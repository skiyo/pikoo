import test from 'node:test';
import assert from 'node:assert/strict';
import { RealtimeInputRuntime } from './node_modules/qwen-audio-agent/server/src/voice/realtime-input-runtime.mjs';
import { installCompanionInput } from './companion-runtime.mjs';

test('silent native audio is valid only in opted-in Google companion mode; transcript, turn cleanup and normal-mode watchdog survive',()=>{
 const old=process.env.PIKOO_COMPANION_MODE,restore=installCompanionInput();
 try {
  for(const [mode,provider,watchdog] of [['on','google-live',0],['off','google-live',1],['on','other',1]]){
   process.env.PIKOO_COMPANION_MODE=mode;
   const events=[],records=[];let expected=0,ended=0;
   const context={turnId:'synthetic-turn'};
   const expect=()=>expected++;
   const send=e=>events.push(e);
   const runtime=new RealtimeInputRuntime({ownerId:'test',sessionId:'test',
    turns:{resolveInput:()=>context,isInputInvalid:()=>false,isStale:()=>false,endSpeech:()=>ended++,completeInput:()=>({context}),commit:()=>{}},
    transcripts:{record:()=>{},parts:()=>[]},inputAssets:{metadataForParts:()=>[]},
    conversationSync:{record:e=>records.push(e)},announcementWindow:{endSpeech:()=>{}},
    send,getFrontend:()=>({provider:{key:provider}}),expectResponseFor:expect,shouldEnsurePermissionResponse:()=>false});
   runtime.handleProviderEvent({type:'input_audio_buffer.speech_stopped',item_id:'input'});
   runtime.handleProviderEvent({type:'conversation.item.input_audio_transcription.completed',item_id:'input',transcript:'A generic test utterance.'});
   assert.equal(expected,watchdog);assert.equal(ended,1);assert.equal(records.length,1);
   assert.equal(events.find(e=>e.type==='voice.state').state,watchdog?'processing':'listening');
   assert.equal(runtime.expectResponseFor,expect);assert.equal(runtime.send,send);
  }
 } finally {restore();if(old===undefined)delete process.env.PIKOO_COMPANION_MODE;else process.env.PIKOO_COMPANION_MODE=old;}
});
