import { RealtimeInputRuntime } from './node_modules/qwen-audio-agent/server/src/voice/realtime-input-runtime.mjs';
import { companionEnabled } from './google-live-compat.mjs';

// Fixed-version composition hook, like context-runtime: never edit the
// installed package. Silence is a valid native proactive-audio outcome, so a
// completed microphone utterance must not start the "missing reply" watchdog.
// Explicit text/tool operations and transport timeouts keep their safeguards.
export function installCompanionInput() {
  const original=RealtimeInputRuntime.prototype.handleProviderEvent;
  function handle(event) {
    if(!companionEnabled() || this.getFrontend()?.provider?.key!=='google-live' ||
       event?.type!=='input_audio_buffer.speech_stopped' || event.reason==='turn_invalid')
      return original.call(this,event);
    const expect=this.expectResponseFor,send=this.send;
    this.expectResponseFor=()=>{};
    this.send=e=>send(e.type==='voice.state'&&e.state==='processing'?{...e,state:'listening'}:e);
    try {return original.call(this,event);}
    finally {this.expectResponseFor=expect;this.send=send;}
  }
  RealtimeInputRuntime.prototype.handleProviderEvent=handle;
  return ()=>{if(RealtimeInputRuntime.prototype.handleProviderEvent===handle)RealtimeInputRuntime.prototype.handleProviderEvent=original;};
}
