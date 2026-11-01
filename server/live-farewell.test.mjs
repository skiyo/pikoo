import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createLiveRuntime,ToolReceipts} from './live-runtime.mjs';
import {LIVE_CAPABILITY,PCM16_CAPABILITY} from './openai-live.mjs';
import {UsageLedger} from './live-usage.mjs';
import {ConversationSync} from './node_modules/qwen-audio-agent/server/src/conversation/conversation-sync.mjs';
const settle=async()=>{for(let i=0;i<8;i++)await Promise.resolve();};
function fixture(t) {
 t.mock.timers.enable({apis:['Date','setInterval','setTimeout'],now:100000});
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'pikoo-farewell-')),sent=[],logs=[];
 let transport,resolveClassification,requests=0;
 const runtime=createLiveRuntime({ownerId:'test',sessionId:'test',send:e=>sent.push(e),voiceAccess:{claim:()=>({granted:true}),isActive:()=>true,release(){},changed(){}},logger:{info:(event,data)=>logs.push({event,...data}),warn(){}}},
  {services:{conversationSync:new ConversationSync()},config:{},ledger:new UsageLedger(),receipts:new ToolReceipts(directory),terra:{request:()=>{requests++;return new Promise(resolve=>resolveClassification=resolve);}},createTransport:options=>transport={id:'test',connect(){options.onEvent({type:'session.started'});},send(){},append16(){},async close(){options.onClose();},event:options.onEvent}});
 runtime.handleClientEvent({type:'connect'},{capabilities:[LIVE_CAPABILITY,PCM16_CAPABILITY]});
 function playback(fields={}) {const ready=sent.filter(e=>e.type==='voice.ready').at(-1);runtime.handleClientEvent({type:'pikoo.playback.status',streamId:ready.streamId,generation:ready.generation,queuedMs:100,dmaMs:50,audible:false,humanSpeaking:false,...fields});}
 return {runtime,sent,logs,playback,event:e=>transport.event(e),requests:()=>requests,
  classify:async result=>{assert(resolveClassification,'Classifier must have started');resolveClassification({text:JSON.stringify(result)});await settle();},
  tick:async ms=>{t.mock.timers.tick(ms);await settle();},
  async close(){await runtime.close();fs.rmSync(directory,{recursive:true,force:true});t.mock.timers.reset();}};
}

test('already spoken goodbye survives a late classifier result and waits for audible playback',async t=>{
 const f=fixture(t);
 try {
  await f.tick(100);f.event({type:'session.input_transcript.delta',delta:'Pikoo，再见。'});
  await f.tick(100);f.event({type:'session.output_transcript.delta',delta:'再见，下次聊。'});
  await f.tick(1500);assert.equal(f.requests(),1);
  f.playback({audible:true,queuedMs:500,dmaMs:100});
  await f.classify({label:'directed',farewell:true});
  await f.tick(1800);assert(!f.sent.some(e=>e.type==='voice.sleep'));
  f.playback({audible:false,queuedMs:100,dmaMs:50});await f.tick(500);
  const sleep=f.sent.filter(e=>e.type==='voice.sleep');assert.equal(sleep.length,1);assert.equal(sleep[0].reason,'farewell');
  assert.equal(sleep[0].preserveContext,true);assert.equal(f.runtime.status().state,'sleeping');
  await f.tick(20000);assert.equal(f.sent.filter(e=>e.type==='voice.sleep').length,1);
 }finally{await f.close();}
});

test('goodbye closes even without an assistant transcript; continuous silence need not drain to zero',async t=>{
 const f=fixture(t);
 try {
  f.event({type:'session.input_transcript.delta',delta:'再见。'});await f.tick(1500);
  await f.classify({label:'directed',farewell:true});
  f.playback({queuedMs:500,dmaMs:100,audible:false});
  await f.tick(4500);assert(!f.sent.some(e=>e.type==='voice.sleep'));
  await f.tick(750);assert.equal(f.sent.filter(e=>e.type==='voice.sleep'&&e.reason==='farewell').length,1);
 }finally{await f.close();}
});

test('mentioning goodbye or saying it to someone else cannot arm voice sleep',async t=>{
 const f=fixture(t);
 try {
  f.event({type:'session.input_transcript.delta',delta:'哥哥，我们跟妈妈说再见。'});await f.tick(1500);
  await f.classify({label:'background',farewell:false});await f.tick(21000);
  assert.equal(f.runtime.status().idle.farewellArmed,false);assert(!f.sent.some(e=>e.type==='voice.sleep'));
  f.event({type:'session.input_transcript.delta',delta:'再见是什么意思？'});await f.tick(1500);
  await f.classify({label:'directed',farewell:false});await f.tick(21000);
  assert.equal(f.runtime.status().idle.farewellArmed,false);assert(!f.sent.some(e=>e.type==='voice.sleep'));
 }finally{await f.close();}
});
