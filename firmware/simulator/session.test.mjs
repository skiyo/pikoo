import test from 'node:test';import assert from 'node:assert/strict';import {DeviceSession} from './session.mjs';
function setup(){let now=0,out=[],drains=[];const s=new DeviceSession({send:x=>out.push(x),stopAudio:()=>{},playAudio:(_,started)=>{started();return new Promise(r=>drains.push(r));},stateChanged:()=>{},now:()=>now});return {s,out,drains,time:n=>now=n};}
test('standby, mute and connecting do not upload',()=>{const {s,out}=setup();s.input('secret');s.wake();s.input('secret');assert.equal(out.length,0);s.receive({type:'voice.ready'});s.input('valid');assert.equal(out.filter(e=>e.type==='input_audio_buffer.append').length,1);s.setMuted(true);s.receive({type:'voice.ready'});s.input('secret');assert.equal(out.filter(e=>e.type==='input_audio_buffer.append').length,1);});
test('done waits for physical drain; old audio after cancel is rejected',async()=>{const {s,out,drains}=setup();s.wake();s.receive({type:'voice.ready'});const p=s.receive({type:'audio.delta',responseId:'a',sampleRate:24000,audio:'AAA='});s.receive({type:'audio.done',responseId:'a'});assert(!out.some(x=>x.type==='playback.ended'));s.cancel();drains[0]();await p;s.receive({type:'voice.ready'});await s.receive({type:'audio.delta',responseId:'a',sampleRate:24000,audio:'AAA='});assert.equal(drains.length,1);assert(!out.some(x=>x.type==='playback.ended'));});
test('normal audio and audio-less tool completion remain distinct',async()=>{const {s,out,drains}=setup();s.wake();s.receive({type:'voice.ready'});s.receive({type:'audio.done',responseId:'tool'});const p=s.receive({type:'audio.delta',responseId:'b',sampleRate:24000,audio:'AAA='});s.receive({type:'audio.done',responseId:'b'});drains[0]();await p;assert.equal(out.filter(x=>x.type==='playback.ended').length,1);});
test('idle clock, occupied state and heartbeat',()=>{const {s,out,time}=setup();s.wake();s.receive({type:'voice.ready'});time(30001);assert(s.idleDue());s.receive({type:'session.ping',event_id:'ping1'});assert.equal(out.at(-1).request_event_id,'ping1');s.disconnect(4002);assert.equal(s.state,'occupied');assert(!s.ready);});
test('cancel after response announcement rejects its first late audio',async()=>{
 const sent=[];let played=0;const s=new DeviceSession({send:e=>sent.push(e),stopAudio:()=>{},playAudio:async()=>{played++},stateChanged:()=>{}});
 s.wake();await s.receive({type:'voice.ready'});await s.receive({type:'response.started',responseId:'late'});s.cancel();await s.receive({type:'voice.ready'});await s.receive({type:'audio.delta',responseId:'late',sampleRate:24000,audio:'AAA='});assert.equal(played,0);
});

test('wake is the first user turn, only once across duplicate readiness, cancel and retry',()=>{
 const {s,out}=setup();s.wake();s.receive({type:'voice.ready'});s.receive({type:'voice.ready'});
 const greetings=()=>out.filter(e=>e.type==='conversation.item.create');
 assert.equal(greetings().length,1);assert.equal(greetings()[0].parts[0].text,'你好 Pikoo');
 s.cancel();s.receive({type:'voice.ready'});assert.equal(greetings().length,1);
 s.disconnect(1006);s.wake(false,{resume:true});s.receive({type:'voice.ready'});assert.equal(greetings().length,1);
 s.stop();s.wake();s.receive({type:'voice.ready'});assert.equal(greetings().length,2);
});
test('only a final user goodbye ends; wait for physical farewell drain then close once',async()=>{
 const {s,out,drains}=setup();let ended=0;s.ended=()=>ended++;s.wake();s.receive({type:'voice.ready'});
 for(const e of [{role:'assistant',content:'再见',type:'transcript.final'},{role:'user',content:'再见',type:'transcript.delta'},{role:'user',content:'不要说再见',type:'transcript.final'},{role:'user',content:'再见是什么意思',type:'transcript.final'}])s.receive(e);
 assert.equal(s.farewell,null);
 s.receive({type:'transcript.final',role:'user',content:'皮酷，再见！',turnId:'bye'});
 const before=out.length;s.input('private-after-bye');assert.equal(out.length,before);
 s.receive({type:'response.started',responseId:'farewell',turnId:'bye'});
 const playing=s.receive({type:'audio.delta',responseId:'farewell',sampleRate:24000,audio:'AAA='});
 s.receive({type:'audio.done',responseId:'farewell'});assert.equal(ended,0);drains[0]();await playing;
 assert.equal(ended,1);assert.equal(s.state,'idle');assert.equal(s.ready,false);assert.equal(s.conversationId,null);
 assert(out.some(e=>e.type==='playback.ended'));s.tick();assert.equal(ended,1);
});
test('goodbye timeout and connection loss return to standby without retry intent',()=>{
 for(const drop of [false,true]){const {s,time}=setup();let ended=0;s.ended=()=>ended++;s.wake();s.receive({type:'voice.ready'});
 s.receive({type:'transcript.final',role:'user',content:'拜拜',turnId:'bye'});
 if(drop)s.disconnect(1006);else{time(19999);s.tick();assert.equal(ended,0);time(20000);s.tick();}
 assert.equal(ended,1);assert.equal(s.state,'idle');assert.equal(s.conversationId,null);}
});
test('Live stream does not require audio.done, ignores old epochs and uses server sleep without losing topic',async()=>{
 const {s,out,drains,time}=setup();let reason; s.ended=r=>reason=r;
 const hello=s.wake();assert(hello.capabilities.includes('pikoo.audio.continuous.v1'));
 s.receive({type:'voice.ready',continuousAudio:true,streamId:'live-a',generation:7});
 assert.equal(out.filter(e=>e.type==='conversation.item.create').length,0);
 const p=s.receive({type:'audio.delta',responseId:'live-a',streamId:'live-a',generation:7,sequence:0,sampleRate:24000,audio:'AAA='});
 drains[0]();await p;s.playbackStatus({audible:false});assert.equal(out.at(-1).type,'pikoo.playback.status');
 time(100000);assert.equal(s.idleDue(),false);
 s.receive({type:'transcript.final',role:'user',content:'哥哥再见'});assert.equal(s.farewell,null);
 s.receive({type:'playback.clear',generation:8});s.receive({type:'voice.ready',continuousAudio:true,streamId:'live-b',generation:9});
 await s.receive({type:'audio.delta',responseId:'live-a',streamId:'live-a',generation:7,sequence:1,sampleRate:24000,audio:'AAA='});assert.equal(drains.length,1);
 const topic=s.conversationId;s.receive({type:'voice.sleep',state:'sleeping'});assert.equal(s.conversationId,topic);assert.equal(reason,'sleep');assert.equal(s.ready,false);
});
