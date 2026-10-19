import fs from 'node:fs';
import path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { containsSensitiveContent } from './node_modules/qwen-audio-agent/server/src/core/sensitive-content.mjs';

const explicit = source => ['gateway-memory-api', 'realtime-tool'].includes(source);
const revision = documents => Object.fromEntries(documents.map(d => [d.scope, d.revision]));
const stamp = value => JSON.stringify(value);
const greeting = /^(你好[，,\s]*(?:皮酷|pikoo)?[！!。.]?|再见[！!。.]?|拜拜[！!。.]?)$/iu;

// Private, bounded outbox. The pinned upstream extractors still validate and
// commit changes; this layer owns delivery, retries and explicit-edit expiry.
export class ContextLearningQueue {
  constructor({ filePath, memory, conversationSync, extractor, audit = null,
    logger = console, now = () => Date.now(), minGapMs = 15000 } = {}) {
    Object.assign(this, { filePath, memory, conversationSync, extractor, audit, logger, now, minGapMs });
    this.jobs = []; this.generations = {}; this.memoryCursor = {}; this.summaryCursor = {};
    this.nextCallAt = 0; this.pausedUntil = 0; this.busy = false; this.closed = false;
    this.summariser = null; this.timer = null; this.active = null;
    if (filePath && fs.existsSync(filePath)) {
      const saved = JSON.parse(fs.readFileSync(filePath, 'utf8'));
      if (saved.version !== 1 || !Array.isArray(saved.jobs) || saved.jobs.length > 100)
        throw new Error('Invalid context learning outbox; preserve and inspect the private file');
      this.generations = saved.generations || {}; this.pausedUntil = Number(saved.pausedUntil) || 0;
      this.jobs = saved.jobs.filter(j => this.valid(j) &&
        stamp(j.revisions) === stamp(revision(memory.list(j.ownerId))));
    }
    this.unsubscribe = memory.subscribe(event => {
      if (explicit(event.source)) this.invalidate(event.ownerId);
    });
  }
  valid(job) {
    return ['memory', 'summary'].includes(job.kind) && typeof job.ownerId === 'string'
      && typeof job.sessionId === 'string' && Array.isArray(job.messages)
      && job.messages.length <= 40 && job.messages.every(m => ['user','assistant'].includes(m.role)
        && typeof m.content === 'string' && m.content.length <= 6000)
      && Number.isFinite(job.nextAt) && job.createdAt > this.now() - 7 * 86400000
      && job.generation === (this.generations[job.ownerId] || 0);
  }
  persist() {
    if (!this.filePath) return;
    fs.mkdirSync(path.dirname(this.filePath), { recursive: true, mode: 0o700 });
    const temporary = this.filePath + '.' + randomUUID() + '.tmp';
    const fd = fs.openSync(temporary, 'wx', 0o600);
    try {
      fs.writeFileSync(fd, JSON.stringify({ version: 1, generations: this.generations,
        pausedUntil: this.pausedUntil, jobs: this.jobs }) + '\n'); fs.fsyncSync(fd);
    } finally { fs.closeSync(fd); }
    fs.renameSync(temporary, this.filePath);
    const directory = fs.openSync(path.dirname(this.filePath), 'r');
    try { fs.fsyncSync(directory); } finally { fs.closeSync(directory); }
  }
  enqueue(kind, args) {
    const cursor = kind === 'memory' ? this.memoryCursor : this.summaryCursor;
    const batch = this.conversationSync.pendingRecords(args, cursor);
    const messages = []; let chars = 0;
    for (const m of (batch?.messages || []).slice(-40).toReversed()) {
      const content = String(m.content || '').trim();
      if (!['user','assistant'].includes(m.role) || !content || containsSensitiveContent(content)) continue;
      if (messages.length && chars + content.length > 6000) break;
      if (content.length > 6000) continue;
      messages.unshift({ id: m.id, role: m.role, content }); chars += content.length;
    }
    if (!messages.some(m => m.role === 'user' && !greeting.test(m.content))) return null;
    if (this.jobs.length >= 100) throw new Error('Context outbox full; new learning batch not consumed');
    const key = createHash('sha256').update(stamp([kind,args.ownerId,args.sessionId,messages])).digest('hex');
    if (!this.jobs.some(j => j.key === key)) {
      this.jobs.push({ key, kind, ownerId: args.ownerId, sessionId: args.sessionId, messages,
        generation: this.generations[args.ownerId] || 0, createdAt: this.now(),
        attempts: 0, nextAt: this.now(), revisions: revision(this.memory.list(args.ownerId)) });
      try { this.persist(); } catch (error) { this.jobs.pop(); throw error; }
    }
    batch.consume(); this.schedule(); return null;
  }
  invalidate(ownerId) {
    this.generations[ownerId] = (this.generations[ownerId] || 0) + 1;
    this.jobs = this.jobs.filter(j => j.ownerId !== ownerId); this.persist();
  }
  // There is no public delete API on the pinned digest pool. For explicit
  // corrections/deletions conservatively clear this owner's topic index.
  // Subsequent summaries only consume post-edit observations, never old text.
  clearSummaries(ownerId) {
    const pool = this.summariser?.digestPool;
    if (!pool) return;
    pool.load();
    if (!(pool.owners instanceof Map) || typeof pool.save !== 'function')
      throw new Error('Pinned digest pool changed; review deletion adapter');
    if (pool.owners.delete(ownerId)) pool.save();
  }
  bindSummariser(summariser) {
    this.summariser = summariser;
    if (summariser) summariser.maybeRun = args => this.enqueue('summary', args);
  }
  start() { this.started = true; this.persist(); this.schedule(); }
  schedule() {
    if (!this.started || this.closed || this.busy || this.timer || !this.jobs.length) return;
    const next = Math.max(this.pausedUntil, this.nextCallAt, Math.min(...this.jobs.map(j => j.nextAt)));
    this.timer = setTimeout(() => {
      this.timer = null; this.active = this.runOne().catch(error => {
        this.logger.error?.('pikoo.context_storage_failed', { code: error?.code || 'outbox_failure' });
      }).finally(() => { this.active = null; });
    }, Math.max(0,next-this.now()));
    this.timer.unref?.();
  }
  async runOne() {
    if (this.busy || this.closed) return;
    const at = this.now();
    if (at < this.pausedUntil || at < this.nextCallAt) { this.schedule(); return; }
    this.jobs = this.jobs.filter(j => this.valid(j));
    const job = this.jobs.find(j => j.nextAt <= at);
    if (!job) { this.persist(); this.schedule(); return; }
    this.busy = true; this.runningOwner = job.ownerId;
    const isCurrent = () => job.generation === (this.generations[job.ownerId] || 0);
    try {
      const executor = job.kind === 'memory' ? this.extractor : this.summariser;
      if (!executor) throw new Error('Context executor not attached');
      // The upstream summariser catches text failures. Capture their cause so
      // a transient provider failure remains pending instead of disappearing.
      const original = executor.llmCall, originalAudit = executor.audit; let callError, processingError;
      executor.audit = { record(event) {
        if (event.op === 'error') processingError = new Error(String(event.error || 'Context processing failed'));
        originalAudit?.record(event);
      } };
      executor.llmCall = async request => {
        try { return await original(request); } catch (error) { callError = error; throw error; }
      };
      try {
        await executor.run({ ownerId: job.ownerId, sessionId: job.sessionId,
          messages: job.messages, turns: job.messages.filter(m => m.role === 'user').length, isCurrent });
        if (callError) throw callError;
        if (processingError) throw processingError;
        // Summariser.run has no write-generation guard. Discard a late summary
        // if a correction/deletion happened while its text request was running.
        if (!isCurrent() && job.kind === 'summary') this.clearSummaries(job.ownerId);
      } finally { executor.llmCall = original; executor.audit = originalAudit; }
      this.jobs = this.jobs.filter(j => j !== job);
      const latest = revision(this.memory.list(job.ownerId));
      for (const pending of this.jobs) if (pending.ownerId === job.ownerId) pending.revisions = latest;
      this.audit?.record({ op: 'observe', ownerId: job.ownerId, scope: 'pikoo_context', reason: job.kind+'_processed' });
    } catch (error) {
      if (isCurrent()) {
        job.attempts++; const message = String(error?.message || error);
        const category = /\b429\b|quota|rate.limit/i.test(message) ? 'quota'
          : /\b40[134]\b|unauthori|api.key|permission.denied/i.test(message) ? 'configuration' : 'temporary';
        job.lastError = category;
        const delay = category === 'configuration' ? 6*3600000
          : Math.min(6*3600000, (category === 'quota' ? 15*60000 : 30000) * 2**Math.min(job.attempts-1,10));
        job.nextAt = this.now() + delay;
        this.pausedUntil = Math.max(this.pausedUntil, job.nextAt);
        this.logger.warn?.('pikoo.context_deferred', { kind: job.kind, category, attempts: job.attempts });
      }
    } finally {
      this.nextCallAt = this.now() + this.minGapMs;
      this.busy = false; this.runningOwner = null; this.persist(); this.schedule();
    }
  }
  health(ownerId = null) { const jobs = ownerId ? this.jobs.filter(j => j.ownerId === ownerId) : this.jobs; return { pending: jobs.length, running: this.busy && (!ownerId || this.runningOwner === ownerId),
    pausedUntil: this.pausedUntil > this.now() ? this.pausedUntil : null,
    deferred: jobs.filter(j => j.lastError).map(j => ({ kind:j.kind, category:j.lastError, attempts:j.attempts })) }; }
  async close() { this.closed = true; clearTimeout(this.timer); this.unsubscribe?.(); await this.active; this.persist(); }
}

export const familyLearningPolicy = [
  '这是家庭共用宠物。自然陈述的稳定家庭事实、长期决定可以整理，不要求说“记住”。',
  '不得从声音或未署名的“我”推断家庭成员；个人偏好只有明确指明对象才归到该成员。',
  '虚构故事、测试剧情、猜测、短期情绪和助手说过的话，不得记成真实家庭事实。',
].join('\n');
