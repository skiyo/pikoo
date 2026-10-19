import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { ContextLearningQueue } from './context-learning.mjs';
import { SessionDigestPool } from './node_modules/qwen-audio-agent/server/src/conversation/session-digest.mjs';
import { beijingConnectionContext } from './time-context.mjs';
import { coreToolHandlers } from './node_modules/qwen-audio-agent/server/src/frontend/tools/features/core-tools.mjs';

function setup(t,{extractor=null, messages=[{id:'m1',role:'user',content:'我们全家长期一起研究天文。'}]}={}) {
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'pikoo-context-test-'));
  t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  let clock=1000000;const listeners=new Set(),consumed=new WeakSet();
  const memory={rev:'a',list(){return [{scope:'memory',revision:this.rev}];},
    subscribe(fn){listeners.add(fn);return ()=>listeners.delete(fn);},
    edit(){this.rev+='b';for(const fn of listeners)fn({ownerId:'owner',source:'realtime-tool'});}};
  const sync={pendingRecords(_args,cursor){return {messages:consumed.has(cursor)?[]:messages,consume:()=>consumed.add(cursor)};}};
  const options={filePath:path.join(dir,'outbox.json'),memory,conversationSync:sync,
    extractor:extractor||{llmCall:async()=>'',async run(){await this.llmCall({});}},
    now:()=>clock,minGapMs:0,logger:{warn(){},error(){}}};
  const queue=new ContextLearningQueue(options);t.after(()=>queue.close());
  return {queue,options,memory,advance:ms=>clock+=ms,args:{ownerId:'owner',sessionId:'session'}};
}
test('one naturally stated fact is durable, retryable and recoverable after restart',async t=>{
  let calls=0;const executor={llmCall:async()=>{if(++calls===1)throw Error('503 unavailable');return '';},async run(){await this.llmCall({});}};
  const s=setup(t,{extractor:executor});s.queue.enqueue('memory',s.args);
  assert.equal(fs.statSync(s.options.filePath).mode&0o777,0o600);
  assert.equal(JSON.parse(fs.readFileSync(s.options.filePath)).jobs.length,1);
  await s.queue.runOne();assert.equal(s.queue.health().pending,1);assert.equal(s.queue.health().deferred[0].category,'temporary');
  await s.queue.close();s.advance(30001);
  const recovered=new ContextLearningQueue(s.options);await recovered.runOne();
  assert.equal(calls,2);assert.equal(recovered.health().pending,0);await recovered.close();
});
test('quota failure pauses all background work and does not silently lose the batch',async t=>{
  let calls=0;const s=setup(t,{extractor:{llmCall:async()=>{calls++;throw Error('429 quota exceeded');},async run(){await this.llmCall({});}}});
  s.queue.enqueue('memory',s.args);await s.queue.runOne();await s.queue.runOne();
  assert.equal(calls,1);assert.equal(s.queue.health().pending,1);assert.equal(s.queue.health().deferred[0].category,'quota');
  assert(s.queue.health().pausedUntil>=1000000+900000);
});
test('explicit edits invalidate queued and in-flight learning before a write',async t=>{
  let resume,written=0;const executor={llmCall:()=>new Promise(r=>resume=r),async run({isCurrent}){await this.llmCall({});if(isCurrent())written++;}};
  const s=setup(t,{extractor:executor});s.queue.enqueue('memory',s.args);
  const running=s.queue.runOne();assert.equal(s.queue.health('another-owner').pending,0);assert.equal(s.queue.health('another-owner').running,false);
  s.memory.edit();resume('old evidence');await running;
  assert.equal(written,0);assert.equal(s.queue.health().pending,0);
});
test('a summary caller swallowing a provider failure still leaves a retry job',async t=>{
  const s=setup(t);s.queue.bindSummariser({llmCall:async()=>{throw Error('503 busy');},async run(){try{await this.llmCall({});}catch{return null;}}});
  s.queue.enqueue('summary',s.args);await s.queue.runOne();assert.equal(s.queue.health().pending,1);
});
test('late summaries cannot reintroduce facts after correction or deletion',async t=>{
  const s=setup(t);const pool=new SessionDigestPool();let resume;
  s.queue.bindSummariser({digestPool:pool,llmCall:()=>new Promise(r=>resume=r),async run(){await this.llmCall({});pool.record({ownerId:'owner',sessionId:'session',topics:['旧信息'],gist:'旧信息',turns:1});}});
  s.queue.enqueue('summary',s.args);const running=s.queue.runOne();s.memory.edit();s.queue.clearSummaries('owner');resume('late');await running;
  assert.equal(pool.count('owner'),0);assert.equal(s.queue.health().pending,0);
});
test('restart rejects an outbox created before a changed document revision',async t=>{
  const s=setup(t);s.queue.enqueue('memory',s.args);await s.queue.close();s.memory.rev='changed-outside-process';
  const recovered=new ContextLearningQueue(s.options);assert.equal(recovered.health().pending,0);await recovered.close();
});
test('greeting-only sessions and sensitive text do not generate learning jobs',t=>{
  const s=setup(t,{messages:[{role:'user',content:'你好皮酷'},{role:'user',content:'我的密码是 example-secret'}]});
  s.queue.enqueue('memory',s.args);assert.equal(s.queue.health().pending,0);
});
test('Beijing connection clock crosses the UTC date boundary and requires fresh time queries',()=>{
  const clock=beijingConnectionContext(new Date('2026-10-19T16:01:00Z'));
  assert.match(clock,/2026年10月20日/);assert.match(clock,/00:01:00/);assert.match(clock,/get_current_time/);
});
test('official current-time tool reads a fresh clock in a long-lived connection',async t=>{
  t.mock.timers.enable({apis:['Date'],now:Date.parse('2026-10-19T15:59:00Z')});
  const output=[];const handlers=coreToolHandlers({getClientContext:()=>({timeZone:'Asia/Shanghai',locale:'zh-CN'}),sendOutput:async(_id,value)=>output.push(value)});
  await handlers.get_current_time({callId:'first'});t.mock.timers.tick(120000);
  await handlers.get_current_time({callId:'later'});
  assert.match(output[0].local_time,/2026年10月19日/);assert.match(output[1].local_time,/2026年10月20日/);
  assert.notEqual(output[0].iso_utc,output[1].iso_utc);assert.equal(output[1].time_zone,'Asia/Shanghai');
});
