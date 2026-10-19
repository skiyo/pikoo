import test from 'node:test';
import assert from 'node:assert/strict';
import {DeviceSession} from './session.mjs';
import {socketRoute} from './socket-route.mjs';
import {loadConversation,saveConversation,key} from './conversation-storage.mjs';
test('disconnect and mute keep conversation; explicit end starts a new one',()=>{
 let id=0;const saved=[];const s=new DeviceSession({send:()=>{},stopAudio:()=>{},playAudio:async()=>{},stateChanged:()=>{},newConversationId:()=>`test-session-${++id}`,conversationChanged:id=>saved.push(id)});
 s.wake();const first=s.conversationId;s.stop({endConversation:false});assert.equal(s.conversationId,first);assert.equal(s.state,'idle');s.wake();s.disconnect(1006);s.wake();assert.equal(s.conversationId,first);
 s.setMuted(true);assert.equal(s.conversationId,first);s.setMuted(false);s.wake();assert.equal(s.conversationId,first);
 s.stop();assert.equal(s.conversationId,null);s.wake();assert.notEqual(s.conversationId,first);assert.deepEqual(saved,[first,null,'test-session-2']);
});
test('tab storage holds only expiring identifier; blocked storage does not prevent operation',()=>{
 const rows=new Map(),storage={getItem:k=>rows.get(k),setItem:(k,v)=>rows.set(k,v),removeItem:k=>rows.delete(k)};
 saveConversation(storage,'test-session-1',1000);assert.equal(loadConversation(storage,2000),'test-session-1');
 assert.deepEqual(JSON.parse(rows.get(key)),{id:'test-session-1',at:1000});assert.equal(loadConversation(storage,86401001),null);assert.equal(loadConversation(storage,500),null);
 saveConversation(storage,null);assert.equal(loadConversation(storage),null);
 const blocked={getItem:()=>{throw Error()},setItem:()=>{throw Error()}};assert.equal(loadConversation(blocked),null);assert.doesNotThrow(()=>saveConversation(blocked,'test-session-1'));
});
test('automatic 30-second sleep stops upload but reconnects to the same topic',()=>{
 let now=0,id=0;const out=[];
 const s=new DeviceSession({send:e=>out.push(e),stopAudio:()=>{},playAudio:async()=>{},stateChanged:()=>{},now:()=>now,newConversationId:()=>`topic-${++id}`});
 s.wake();s.receive({type:'voice.ready'});const original=s.conversationId;
 now=29999;assert.equal(s.sleepIfIdle(),false);assert.equal(s.ready,true);
 now=30000;assert.equal(s.sleepIfIdle(),true);assert.equal(s.state,'idle');assert.equal(s.ready,false);
 const before=out.length;s.input('must-stay-local');assert.equal(out.length,before);
 s.wake();assert.equal(s.conversationId,original);s.receive({type:'voice.ready'});
 s.disconnect(1006);s.wake(undefined,{resume:true});assert.equal(s.conversationId,original);
 s.stop();s.wake();assert.notEqual(s.conversationId,original);
});
test('conversation query remains bounded, local and unambiguous',()=>{
 const origin='http://127.0.0.1:8793';assert.deepEqual(socketRoute('/device?conversationId=test-session-1',origin),{path:'/device',conversationId:'test-session-1'});
 assert.deepEqual(socketRoute('/device',origin),{path:'/device'});
 for(const url of ['/device?conversationId=../other','/device?conversationId=abcdefghi&conversationId=duplicate','/device?token=not-allowed','/eyes?conversationId=test-session-1','//evil.invalid/device','/device?conversationId='+ 'a'.repeat(81)])assert.equal(socketRoute(url,origin),null);
});
