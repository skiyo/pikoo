import test from 'node:test';
import assert from 'node:assert/strict';
import { liveSchema,liveInputConfig,pikooGoogleLiveProvider,liveLanguageInstructions } from './google-live-compat.mjs';
test('every new or reconnected Live session carries the bilingual policy without a single-language API field',()=>{
 const original={persona:{},frontend:{}};
 for(let n=0;n<2;n++){
  const session=pikooGoogleLiveProvider.buildSession({agentContext:original,sessionOptions:{}});
  assert.equal(session.systemInstruction.parts.at(-1).text,liveLanguageInstructions);
  assert.match(liveLanguageInstructions,/Neither language has priority/);
  assert.match(liveLanguageInstructions,/English-practice request/);
  assert.match(liveLanguageInstructions,/Do not force an English conversation back into Mandarin/);
  assert.match(liveLanguageInstructions,/Unclear speech, silence, background sounds/);
  assert.equal(session.generationConfig.speechConfig?.languageCode,undefined);
  assert.deepEqual(session.generationConfig.responseModalities,['AUDIO']);
  for(const fn of session.tools.flatMap(t=>t.functionDeclarations)){
   if(['web_search','fetch_url','notes'].includes(fn.name))assert.equal(fn.behavior,'BLOCKING');
  }
  assert.ok(session.systemInstruction.parts.some(p=>p.text.includes('Asia/Shanghai')));
 }
 assert.deepEqual(original,{persona:{},frontend:{}});
});
test('optional speech detection tuning preserves interruption and rejects invalid settings',()=>{
 const base={activityHandling:'START_OF_ACTIVITY_INTERRUPTS',automaticActivityDetection:{disabled:false,silenceDurationMs:600}};
 assert.equal(liveInputConfig(base,{}),base);
 const out=liveInputConfig(base,{PIKOO_GOOGLE_LIVE_START_SENSITIVITY:'low',PIKOO_GOOGLE_LIVE_PREFIX_PADDING_MS:'180'});
 assert.equal(out.activityHandling,'START_OF_ACTIVITY_INTERRUPTS');
 assert.deepEqual(out.automaticActivityDetection,{disabled:false,silenceDurationMs:600,startOfSpeechSensitivity:'START_SENSITIVITY_LOW',prefixPaddingMs:180});
 assert.equal(base.automaticActivityDetection.startOfSpeechSensitivity,undefined);
 assert.throws(()=>liveInputConfig(base,{PIKOO_GOOGLE_LIVE_START_SENSITIVITY:'off'}));
 assert.throws(()=>liveInputConfig(base,{PIKOO_GOOGLE_LIVE_PREFIX_PADDING_MS:'NaN'}));
});
test('Gemini schema retains tool constraints and never mutates the original',()=>{
 const input={type:'object',additionalProperties:false,required:['edits'],properties:{edits:{type:'array',items:{type:'object',additionalProperties:false,required:['old_text'],properties:{old_text:{type:'string'},new_text:{type:'string'}}}}}};
 const copy=structuredClone(input);const output=liveSchema(input);
 assert.deepEqual(input,copy);assert.equal(JSON.stringify(output).includes('additionalProperties'),false);
 assert.deepEqual(output.required,['edits']);assert.deepEqual(output.properties.edits.items.required,['old_text']);
 assert.equal(output.properties.edits.items.properties.old_text.type,'string');
});
test('voice runtime provider preserves the Google native model and contract',()=>{
 assert.equal(pikooGoogleLiveProvider.key,'google-live');
 assert.equal(pikooGoogleLiveProvider.inputSampleRate,16000);
 assert.equal(pikooGoogleLiveProvider.outputSampleRate,24000);
 assert.equal(pikooGoogleLiveProvider.capabilities.automaticToolResponses,true);
});
import { wrapGoogleProtocol } from './google-live-compat.mjs';
import { createGoogleLiveProtocol } from './node_modules/qwen-audio-agent/server/src/voice/providers/google-live-protocol.mjs';
import { RealtimeFrontend } from './node_modules/qwen-audio-agent/server/src/voice/realtime-provider.mjs';
test('real frontend delivery writes no Google frame for a cancelled late result',async()=>{
 const frames=[];const f=new RealtimeFrontend({provider:pikooGoogleLiveProvider});
 f.ready=true;f.ws={readyState:1,send:wire=>frames.push(JSON.parse(wire))};
 f.protocol.normalizeIncoming({toolCall:{functionCalls:[{id:'slow',name:'fetch_url',args:{url:'https://example.org'}}]}});
 f.protocol.responseCancel();await f.sendFunctionOutput('slow',{content:'late page'});
 assert.deepEqual(frames,[]);
 f.protocol.normalizeIncoming({toolCall:{functionCalls:[{id:'fresh',name:'notes',args:{action:'lists'}}]}});
 await f.sendFunctionOutput('fresh',{status:'empty'});
 assert.equal(frames.length,1);assert.equal(frames[0].toolResponse.functionResponses[0].id,'fresh');
 f.ws=null;
});
test('native tool results cannot restart speech after cancellation or barge-in',()=>{
 for(const cancel of [p=>p.responseCancel(),p=>p.normalizeIncoming({toolCallCancellation:{ids:['old']}}),p=>p.normalizeIncoming({serverContent:{interrupted:true}})]){
  const p=wrapGoogleProtocol(createGoogleLiveProtocol());
  p.normalizeIncoming({toolCall:{functionCalls:[{id:'old',name:'web_search',args:{query:'cat'}}]}});
  cancel(p);
  assert.equal(p.conversationItemCreate(p.functionOutputItem('old',{results:[]})),null);
  p.normalizeIncoming({toolCall:{functionCalls:[{id:'new',name:'notes',args:{action:'lists'}}]}});
  const out=p.conversationItemCreate(p.functionOutputItem('new',{status:'ok'}));
  assert.equal(out.toolResponse.functionResponses[0].name,'notes');
  assert.equal(p.conversationItemCreate(p.functionOutputItem('new',{status:'ok'})),null);
 }
});
test('split Gemini speech becomes one completed transcript before response audio',()=>{
 const p=wrapGoogleProtocol(createGoogleLiveProtocol());
 const first=p.normalizeIncoming({serverContent:{inputTranscription:{text:'我们家'}}});
 const next=p.normalizeIncoming({serverContent:{inputTranscription:{text:'每周读书。'}}});
 const response=p.normalizeIncoming({serverContent:{modelTurn:{parts:[{inlineData:{data:'AAA=',mimeType:'audio/pcm;rate=24000'}}]}}});
 const all=[...first,...next,...response];const start=all.filter(e=>e.type==='input_audio_buffer.speech_started');
 const complete=all.find(e=>e.type==='conversation.item.input_audio_transcription.completed');
 assert.equal(start.length,1);assert.equal(complete.item_id,start[0].item_id);assert.equal(complete.transcript,'我们家每周读书。');
 assert.ok(all.indexOf(complete)<all.findIndex(e=>e.type==='response.audio.delta'));
});
test('Gemini barge-in closes old response before opening the new voice turn',()=>{
 const p=wrapGoogleProtocol(createGoogleLiveProtocol());
 p.normalizeIncoming({serverContent:{modelTurn:{parts:[{inlineData:{data:'AAA=',mimeType:'audio/pcm;rate=24000'}}]}}});
 const events=p.normalizeIncoming({serverContent:{interrupted:true}});
 const done=events.find(e=>e.type==='response.done');assert.equal(done.response.status,'cancelled');
 assert.ok(events.indexOf(done)<events.findIndex(e=>e.type==='input_audio_buffer.speech_started'));
 const result=p.normalizeIncoming({serverContent:{inputTranscription:{text:'停一下'}}});
 assert.equal(result.filter(e=>e.type==='input_audio_buffer.speech_started').length,0);
});
test('Gemini output transcript is finalized once so history and summaries retain it',()=>{
 const p=wrapGoogleProtocol(createGoogleLiveProtocol());
 p.normalizeIncoming({serverContent:{modelTurn:{parts:[{inlineData:{data:'AAA=',mimeType:'audio/pcm;rate=24000'}}]},outputTranscription:{text:'你好'}}});
 p.normalizeIncoming({serverContent:{outputTranscription:{text:'，世界。'}}});
 const events=p.normalizeIncoming({serverContent:{turnComplete:true}});
 const done=events.find(e=>e.type==='response.audio_transcript.done');
 assert.equal(done.transcript,'你好，世界。');assert.ok(events.indexOf(done)<events.findIndex(e=>e.type==='response.done'));
 assert.equal(p.normalizeIncoming({serverContent:{turnComplete:true}}).filter(e=>e.type==='response.audio_transcript.done').length,0);
});
test('audio transcript commits before tools run, preserving explicit edit learning boundaries',()=>{
 const p=wrapGoogleProtocol(createGoogleLiveProtocol());p.normalizeIncoming({serverContent:{inputTranscription:{text:'请忘记城堡'}}});
 const events=p.normalizeIncoming({toolCall:{functionCalls:[{id:'x',name:'memory',args:{}}]}});
 assert.ok(events.findIndex(e=>e.type==='conversation.item.input_audio_transcription.completed')<events.findIndex(e=>e.type==='response.function_call_arguments.done'));
});
