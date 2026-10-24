import test from 'node:test';
import assert from 'node:assert/strict';
import { guardSilentOutput, isSilentMarker, filterSilentHistory, installSilentHistoryFilter } from './silence-output.mjs';
import { wrapGoogleProtocol, pikooGoogleLiveProvider } from './google-live-compat.mjs';
import { createGoogleLiveProtocol } from './node_modules/qwen-audio-agent/server/src/voice/providers/google-live-protocol.mjs';
import { RealtimeFrontend } from './node_modules/qwen-audio-agent/server/src/voice/realtime-provider.mjs';

const protocol = options => guardSilentOutput(wrapGoogleProtocol(createGoogleLiveProtocol()), options);
const audio = { modelTurn: { parts: [{ inlineData: { data: 'AAA=', mimeType: 'audio/pcm;rate=24000' } }] } };
const accept = (p, content) => p.normalizeIncoming({ serverContent: content });
const visible = events => events.filter(e => /response\.(audio|text)/.test(e.type));

test('only reserved standalone output markers are metadata, not English learning or user speech', () => {
  for (const text of ['<no speech>', '[NO_SPEECH]', ' <no-speak> ', '<no speech>{pause}', '<no speech>{pause}{pause}']) assert.ok(isSilentMarker(text));
  for (const text of ['no speech', 'The phrase no speech means silence.', 'There is <no speech> in this quote.'])
    assert.equal(isSilentMarker(text), false);
  const p = protocol();
  const events = accept(p, { inputTranscription: { text: 'What does no speech mean?', finished: true } });
  assert.ok(events.some(e => e.transcript === 'What does no speech mean?'));
});

test('observed native pause suffix is metadata even when it arrives in the first full transcript chunk', () => {
  for (const text of ['<no speech>{pause}', '<no speech>{pa', '<no speech>{pause}{pause}']) {
    const p = protocol();
    const events = accept(p, { ...audio, outputTranscription: { text }, turnComplete: true });
    assert.deepEqual(visible(events), []);
    assert.equal(p.silenceStatus().silentTurns, 1);
  }
});

test('split silence marker drops earlier PCM, text and history payload while retaining terminal lifecycle', () => {
  const p = protocol(), events = [];
  events.push(...accept(p, audio));
  for (const text of ['<no', ' speech', '>']) events.push(...accept(p, { outputTranscription: { text } }));
  events.push(...accept(p, { turnComplete: true }));
  assert.deepEqual(visible(events), []);
  assert.equal(events.filter(e => e.type === 'response.created').length, 1);
  assert.equal(events.filter(e => e.type === 'response.done').length, 1);
  assert.equal(p.silenceStatus().silentTurns, 1);
});

test('marker in the same audio frame is silent and the next natural follow-up needs no name', () => {
  const p = protocol();
  assert.deepEqual(visible(accept(p, { ...audio, outputTranscription: { text: '<no speech>' }, turnComplete: true })), []);
  const next = accept(p, { inputTranscription: { text: 'And then?', finished: true },
    ...audio, outputTranscription: { text: 'Then they went home.' }, turnComplete: true });
  assert.equal(next.filter(e => e.type === 'response.audio.delta').length, 1);
  assert.equal(next.find(e => e.type === 'response.audio_transcript.done').transcript, 'Then they went home.');
});

test('normal opening audio is held only until ordinary transcription and is released intact in order', () => {
  const p = protocol();
  assert.deepEqual(visible(accept(p, audio)), []);
  const events = accept(p, { ...audio, outputTranscription: { text: 'Hello!' } });
  assert.deepEqual(events.filter(e => e.type === 'response.audio.delta').map(e => e.delta), ['AAA=', 'AAA=']);
  assert.ok(events.some(e => e.type === 'response.audio_transcript.delta'));
});

test('ordinary explanations and legitimate audio-only turns survive', () => {
  const p = protocol();
  const events = accept(p, { ...audio, outputTranscription: { text: 'No speech means nobody is talking.' }, turnComplete: true });
  assert.equal(events.filter(e => e.type === 'response.audio.delta').length, 1);
  assert.deepEqual(visible(accept(p, audio)), []);
  assert.equal(accept(p, { turnComplete: true }).filter(e => e.type === 'response.audio.delta').length, 1);
  assert.equal(p.silenceStatus().audioOnlyTurns, 1);
});

test('interruption, cancellation and late old output never flush withheld audio', () => {
  for (const cancel of [p => p.responseCancel(), p => accept(p, { interrupted: true })]) {
    const p = protocol(); const first = accept(p, audio); const id = first.find(e => e.type === 'response.created').response.id;
    const result = cancel(p);
    if (Array.isArray(result)) assert.deepEqual(visible(result), []);
    const done = accept(p, { turnComplete: true }); assert.deepEqual(visible(done), []);
    assert.ok(id);
  }
});

test('a retired response ID cannot reintroduce late PCM or transcript after cancellation', () => {
  const p = guardSilentOutput({ normalizeIncoming: event => event, responseCancel: () => null });
  p.normalizeIncoming({ type: 'response.created', response: { id: 'old' } });
  p.normalizeIncoming({ type: 'response.audio.delta', response_id: 'old', delta: 'AAA=' });
  p.responseCancel();
  assert.deepEqual(p.normalizeIncoming({ type: 'response.audio.delta', response_id: 'old', delta: 'AAA=' }), []);
  assert.deepEqual(p.normalizeIncoming({ type: 'response.audio_transcript.delta', response_id: 'old', delta: 'Late' }), []);
});

test('initial buffering is bounded and overflow does not emit a clipped answer or poison the next turn', () => {
  const p = protocol({ maxPendingBytes: 3 });
  assert.deepEqual(visible(accept(p, audio)), []);
  assert.deepEqual(visible(accept(p, { outputTranscription: { text: 'Hello' }, turnComplete: true })), []);
  assert.equal(p.silenceStatus().overflowTurns, 1);
  const next = accept(p, { outputTranscription: { text: 'Hi' }, turnComplete: true });
  assert.ok(next.some(e => e.type === 'response.audio_transcript.done'));
});

test('truncated metadata never becomes a spoken partial placeholder', () => {
  const p = protocol(); accept(p, audio);
  const events = [...accept(p, { outputTranscription: { text: '<no spe' } }), ...accept(p, { turnComplete: true })];
  assert.deepEqual(visible(events), []);
});

test('real frontend clears response ownership after a suppressed turn and can handle the next reply', () => {
  const f = new RealtimeFrontend({ provider: pikooGoogleLiveProvider });
  f.protocol = protocol();
  const first = f.handleProviderEvent({ serverContent: { ...audio, outputTranscription: { text: '<no speech>' }, turnComplete: true } });
  assert.deepEqual(visible(first), []); assert.equal(f.activeResponses.size, 0);
  const second = f.handleProviderEvent({ serverContent: { ...audio, outputTranscription: { text: '你好。' }, turnComplete: true } });
  assert.equal(second.filter(e => e.type === 'response.audio.delta').length, 1);
  assert.equal(f.activeResponses.size, 0);
});

test('silent history filtering keeps user quotations and real assistant messages without editing source history', async () => {
  const recent = [{ role: 'assistant', content: '<no speech>' }, { role: 'user', content: '<no speech>' },
    { role: 'assistant', content: 'We were talking about cats.' }];
  const copy = structuredClone(recent);
  assert.deepEqual(filterSilentHistory(recent), recent.slice(1)); assert.deepEqual(recent, copy);
  const restore = installSilentHistoryFilter();
  try {
    const f = new RealtimeFrontend({ provider: pikooGoogleLiveProvider, agentContext: { recentMessages: recent } });
    let injected; f.createConversationItem = async item => { injected = item; };
    await f.restoreRecentConversation();
    const text = injected.content[0].text;
    assert.doesNotMatch(text, /助手: <no speech>/);
    assert.match(text, /用户: <no speech>/); assert.match(text, /cats/);
    assert.deepEqual(recent, copy);
  } finally { restore(); }
});

test('native tool requests remain executable without being mistaken for speech placeholders', () => {
  const p = protocol();
  const events = p.normalizeIncoming({ toolCall: { functionCalls: [{ id: 'search', name: 'web_search', args: { query: 'weather' } }] } });
  assert.equal(events.filter(e => e.type === 'response.function_call_arguments.done').length, 1);
  assert.ok(p.conversationItemCreate(p.functionOutputItem('search', { results: [] })));
});
