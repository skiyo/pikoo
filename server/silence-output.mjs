import { RealtimeFrontend } from './node_modules/qwen-audio-agent/server/src/voice/realtime-provider.mjs';

const markers = ['<nospeech>', '[nospeech]', '<nospeak>', '[nospeak]'];
const compact = text => String(text || '').trim().toLowerCase().replace(/[\s_-]+/g, '');
export function isSilentMarker(text) {
  const value = compact(text);
  return markers.some(marker => {
    if (!value.startsWith(marker)) return false;
    let suffix = value.slice(marker.length);
    while (suffix.startsWith('{pause}')) suffix = suffix.slice(7);
    return suffix === '' || '{pause}'.startsWith(suffix);
  });
}
const isSilentPrefix = text => markers.some(marker => marker.startsWith(compact(text)));

export function filterSilentHistory(messages) {
  if (!Array.isArray(messages)) return messages;
  const filtered = messages.filter(m => m.role !== 'assistant' || !isSilentMarker(m.content));
  return filtered.length === messages.length ? messages : filtered;
}

// Composition hook for pinned 2.0.1: retain the original on-disk history,
// but do not teach the next Live connection to repeat prior silence labels.
export function installSilentHistoryFilter() {
  const original = RealtimeFrontend.prototype.restoreRecentConversation;
  function restore(...args) {
    if (this.provider?.key === 'google-live') {
      const recentMessages = filterSilentHistory(this.agentContext.recentMessages);
      if (recentMessages !== this.agentContext.recentMessages)
        this.agentContext = { ...this.agentContext, recentMessages };
    }
    return original.apply(this, args);
  }
  RealtimeFrontend.prototype.restoreRecentConversation = restore;
  return () => { if (RealtimeFrontend.prototype.restoreRecentConversation === restore)
    RealtimeFrontend.prototype.restoreRecentConversation = original; };
}

// Gemini may emit the reserved <no speech> label on a silent turn. It is
// protocol metadata, not dialogue. Hold only the initial output until its
// transcript distinguishes ordinary speech from that label. No audio is
// decoded or retained after release; no name/addressee keyword gate is added.
export function guardSilentOutput(base, { maxPendingBytes = 524288, onSuppressed = () => {} } = {}) {
  if (!Number.isInteger(maxPendingBytes) || maxPendingBytes < 1 || maxPendingBytes > 2097152)
    throw new Error('Invalid initial output buffer limit');
  const states = new Map(), retired = new Set();
  const stats = { silentTurns: 0, overflowTurns: 0, maxHeldBytes: 0, audioOnlyTurns: 0 };
  const idOf = e => e.response_id || e.response?.id || '';
  const payload = new Set(['response.audio.delta', 'response.text.delta',
    'response.text.done', 'response.audio_transcript.delta', 'response.audio_transcript.done']);
  const retire = id => {
    retired.add(id);
    if (retired.size > 64) retired.delete(retired.values().next().value);
  };
  function state(id) {
    if (!states.has(id)) {
      if (states.size >= 8) {
        const oldest = states.keys().next().value;
        states.delete(oldest); retire(oldest);
      }
      states.set(id, { mode: 'pending', held: [], bytes: 0, transcript: '', text: '' });
    }
    return states.get(id);
  }
  function discard(s, reason) {
    s.mode = 'silent'; s.held = []; s.bytes = 0;
    if (reason === 'marker') stats.silentTurns++; else stats.overflowTurns++;
    onSuppressed({ reason });
  }
  function release(s, out) {
    out.push(...s.held); s.held = []; s.bytes = 0; s.mode = 'speech';
  }
  return { ...base,
    silenceStatus: () => ({ ...stats }),
    responseCancel(...args) {
      for (const id of states.keys()) retire(id);
      states.clear();
      return base.responseCancel(...args);
    },
    normalizeIncoming(raw) {
      const value = base.normalizeIncoming(raw);
      const events = !value ? [] : Array.isArray(value) ? value : [value];
      const out = [];
      for (const event of events) {
        const id = idOf(event);
        if (!id) { out.push(event); continue; }
        if (event.type === 'response.created') {
          if (!retired.has(id)) { state(id); out.push(event); }
          continue;
        }
        if (event.type === 'response.done') {
          const s = states.get(id);
          if (s?.mode === 'pending' && event.response?.status === 'completed') {
            const text = compact(s.transcript || s.text);
            if (text && (isSilentMarker(text) || isSilentPrefix(text))) discard(s, 'marker');
            // Audio-only providers still work. With transcription enabled,
            // this fallback waits for turn completion rather than guessing.
            if (s.mode === 'pending') {
              if (s.held.some(e => e.type === 'response.audio.delta')) stats.audioOnlyTurns++;
              release(s, out);
            }
          }
          states.delete(id); retire(id); out.push(event); continue;
        }
        if (!payload.has(event.type)) { out.push(event); continue; }
        if (retired.has(id)) continue;
        const s = state(id);
        if (s.mode === 'silent') continue;
        if (s.mode === 'speech') { out.push(event); continue; }
        if (event.type === 'response.audio_transcript.delta') s.transcript += event.delta || '';
        if (event.type === 'response.audio_transcript.done') s.transcript = event.transcript || s.transcript;
        if (event.type === 'response.text.delta') s.text += event.delta || '';
        if (event.type === 'response.text.done') s.text = event.text || s.text;
        s.held.push(event);
        s.bytes += String(event.delta || event.transcript || event.text || '').length;
        stats.maxHeldBytes = Math.max(stats.maxHeldBytes, s.bytes);
        if (s.bytes > maxPendingBytes) { discard(s, 'initial_output_limit'); continue; }
        const text = compact(s.transcript || s.text);
        if (isSilentMarker(text)) discard(s, 'marker');
        else if (text && !isSilentPrefix(text)) release(s, out);
      }
      return out;
    },
  };
}
