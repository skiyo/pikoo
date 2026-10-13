import { randomUUID } from 'node:crypto';
import { googleLiveProvider } from './node_modules/qwen-audio-agent/server/src/voice/providers/google-live.mjs';
// Gemini Live v1beta rejects JSON Schema's additionalProperties inside Schema.
// Validation still runs in the upstream memory/tool runtime; only its wire declaration changes.
export function liveSchema(value) {
  if (Array.isArray(value)) return value.map(liveSchema);
  if (!value || typeof value !== 'object') return value;
  return Object.fromEntries(Object.entries(value).filter(([key])=>key!=='additionalProperties').map(([key,child])=>[key,liveSchema(child)]));
}
export function wrapGoogleProtocol(base) {
  let input = null;
  const list = x => !x ? [] : Array.isArray(x) ? x : [x];
  function begin(out) {
    if (input) return;
    input={id:'google_input_'+randomUUID(),text:''};
    out.push({type:'input_audio_buffer.speech_started',item_id:input.id});
  }
  function finish(out) {
    if(!input)return;
    out.push({type:'input_audio_buffer.speech_stopped',item_id:input.id});
    out.push({type:'conversation.item.input_audio_transcription.completed',item_id:input.id,transcript:input.text});
    input=null;
  }
  const assistantText=new Map();
  function decorate(events){
    const result=[];
    for(let e of list(events)){
      if(e.type==='response.audio_transcript.delta')assistantText.set(e.response_id,(assistantText.get(e.response_id)||'')+(e.delta||''));
      if(e.type==='response.audio_transcript.done'){
        e={...e,transcript:(assistantText.get(e.response_id)||'')+(e.transcript||'')};
        assistantText.delete(e.response_id);
      }
      if(e.type==='response.done'){
        const text=assistantText.get(e.response.id);
        if(text&&e.response.status==='completed')result.push({type:'response.audio_transcript.done',response_id:e.response.id,transcript:text});
        assistantText.delete(e.response.id);
      }
      result.push(e);
    }
    return result;
  }
  return {...base, normalizeIncoming(event) {
    const content=event?.serverContent;
    if(!content){
      if(event?.toolCall && input){const out=[];finish(out);out.push(...list(base.normalizeIncoming(event)));return decorate(out);}
      return decorate(base.normalizeIncoming(event));
    }
    const out=[];
    // Gemini reports interruption itself. Finish the old response before the
    // speech event reaches Gateway, avoiding a second upstream cancellation.
    if(content.interrupted){
      out.push(...list(base.normalizeIncoming({...event,serverContent:{...content,turnComplete:true,inputTranscription:undefined}})));
      begin(out);
      return decorate(out);
    }
    if(content.inputTranscription?.text){
      begin(out);input.text+=content.inputTranscription.text;
      out.push({type:'conversation.item.input_audio_transcription.delta',item_id:input.id,text:input.text});
    }
    if(content.modelTurn||content.turnComplete||content.inputTranscription?.finished)finish(out);
    const clean={...content};delete clean.inputTranscription;
    const normalized=list(base.normalizeIncoming({...event,serverContent:clean}));
    out.push(...normalized.filter(e=>e.type));
    return decorate(out);
  }};
}
export const pikooGoogleLiveProvider = {
  ...googleLiveProvider,
  createProtocol: () => wrapGoogleProtocol(googleLiveProvider.createProtocol()),
  buildSession(args) {
    const session=googleLiveProvider.buildSession(args);
    return {...session,tools:session.tools.map(tool=>({...tool,functionDeclarations:tool.functionDeclarations.map(fn=>({...fn,parameters:liveSchema(fn.parameters)}))}))};
  },
};
