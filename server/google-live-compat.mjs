import { randomUUID } from 'node:crypto';
import { googleLiveProvider } from './node_modules/qwen-audio-agent/server/src/voice/providers/google-live.mjs';
import { beijingConnectionContext } from './time-context.mjs';
import { guardSilentOutput } from './silence-output.mjs';
export const liveIdentityInstructions = [
  '# Pikoo identity',
  'Your name is Pikoo, a friendly desktop AI pet shared by the family. Always write your name as Pikoo, including in Mandarin replies; never translate it into 皮酷, 皮库 or another Chinese alias.',
  'When speaking, pronounce Pikoo as pee-koo: pī kū, two level syllables. Do not pronounce your name as pí kù. Earlier transcripts or greetings using a Chinese spelling do not change your name.',
].join('\n');
export const liveCompanionInstructions = [
  '# Quiet family companion mode',
  'While this explicitly awakened session stays connected, listen quietly. Family members may be talking to each other, to a television or to someone else. Those conversations are context, not instructions to you.',
  'Speak when someone addresses Pikoo, asks for your opinion or help, or clearly continues an exchange with you. During an ongoing exchange, follow-up answers and questions need not repeat your name. A wake greeting addressed to you deserves one short friendly greeting.',
  'When speech is not directed to you, or the intended listener is uncertain, produce no speech, no acknowledgement and no clarification question. Do not say that you will stay silent. Background speech and noise are not requests. Do not interrupt family conversations with unsolicited comments.',
  'When no one is speaking, remain quiet. Silence means no spoken content; never vocalize a status, placeholder, control label or explanation of your silence.',
  'Do not execute search, list edits or other actions merely because family members discuss doing them. Only carry out requests clearly directed to you. Stable, explicitly stated family facts may use the existing memory rules; never infer identities or private preferences from overheard ambiguous speech.',
  'When explicitly told goodbye or asked to end the conversation, briefly say goodbye. When invited back into the conversation, use the relevant context you heard without claiming to have heard anything while disconnected or muted.',
].join('\n');
export function companionEnabled(env = process.env) {
  const value=String(env.PIKOO_COMPANION_MODE || 'off').trim().toLowerCase();
  if(!['on','off'].includes(value))throw new Error('PIKOO_COMPANION_MODE must be on or off');
  return value==='on';
}
// The deployed v1beta endpoint rejects proactivity at setup (1007), while
// the same model/key accepts it through v1alpha. Keep ordinary mode on its
// original endpoint; pin this opt-in feature to the endpoint actually tested.
export function liveEndpoint(value,companion) {
  if(!companion)return value;
  const url=new URL(value);
  if(url.hostname!=='generativelanguage.googleapis.com' ||
      !/^\/ws\/google\.ai\.generativelanguage\.v1(?:alpha|beta)\.GenerativeService\.BidiGenerateContent$/.test(url.pathname))
    throw new Error('Companion mode requires the verified Google Live endpoint');
  url.pathname=url.pathname.replace('.v1beta.','.v1alpha.');
  return url.toString();
}
// Native Live audio does not accept an explicit language-code restriction.
// https://ai.google.dev/gemini-api/docs/live-api/capabilities#supported-languages
export const liveLanguageInstructions = [
  '# Pikoo output language policy',
  'Speak and write only in Mandarin Chinese and English. Neither language has priority.',
  'Follow the language the user chooses in the current conversation: respond in Mandarin to Mandarin conversation, and in English to English conversation or an English-practice request.',
  'For English learning, continue naturally in English; use Mandarin explanations or bilingual examples when requested or helpful. Do not force an English conversation back into Mandarin.',
  'Mixed Mandarin and English is allowed. Do not speak, quote, imitate, or switch to any third language, including when asked to translate into one; explain this bilingual scope in Mandarin or English instead.',
  'Unclear speech, silence, background sounds, and uncertain transcription are not requests to change language or reasons to break quiet companion mode. Only when clarification is appropriate for a request directed to you, ask briefly in the last clearly chosen supported language; if none is established, ask briefly in Mandarin and English.',
  'Apply this policy to spoken audio and written replies, including greetings, tool results, and replies after reconnection. Do not treat it as a fact about any individual family member.',
].join('\n');
// Gemini Live v1beta rejects JSON Schema's additionalProperties inside Schema.
// Validation still runs in the upstream memory/tool runtime; only its wire declaration changes.
export function liveSchema(value) {
  if (Array.isArray(value)) return value.map(liveSchema);
  if (!value || typeof value !== 'object') return value;
  return Object.fromEntries(Object.entries(value).filter(([key])=>key!=='additionalProperties').map(([key,child])=>[key,liveSchema(child)]));
}
// Optional server-side tuning; keep automatic detection and natural barge-in.
// https://ai.google.dev/api/live#AutomaticActivityDetection
export function liveInputConfig(base = {}, env = process.env) {
  const sensitivity=String(env.PIKOO_GOOGLE_LIVE_START_SENSITIVITY || '').trim().toLowerCase();
  const padding=env.PIKOO_GOOGLE_LIVE_PREFIX_PADDING_MS;
  if(!sensitivity && padding===undefined)return base;
  if(sensitivity && !['low','high'].includes(sensitivity))throw new Error('Invalid Google Live speech sensitivity');
  const ms=padding===undefined?undefined:Number(padding);
  if(ms!==undefined && (!Number.isInteger(ms)||ms<20||ms>1000))throw new Error('Invalid Google Live speech padding');
  return {...base,automaticActivityDetection:{...base.automaticActivityDetection,
    ...(sensitivity?{startOfSpeechSensitivity:`START_SENSITIVITY_${sensitivity.toUpperCase()}`} : {}),
    ...(ms!==undefined?{prefixPaddingMs:ms}:{}),
  }};
}
export function wrapGoogleProtocol(base) {
  let input = null;
  const pendingTools=new Set();
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
  return {...base,
    responseCancel(...args){pendingTools.clear();return base.responseCancel(...args);},
    conversationItemCreate(item,options){
      if(item?.type!=='function_call_output')return base.conversationItemCreate(item,options);
      const current=pendingTools.delete(String(item.call_id||''));
      const payload=base.conversationItemCreate(item,options);
      if(current)return payload;
      // Google resumes speech as soon as toolResponse arrives. Do not send a
      // cancelled result; consume the base adapter's automatic-response flag.
      base.responseCreate({});return null;
    },
    normalizeIncoming(event) {
    const content=event?.serverContent;
    if(content?.interrupted)pendingTools.clear();
    for(const id of event?.toolCallCancellation?.ids||[])pendingTools.delete(String(id));
    for(const call of event?.toolCall?.functionCalls||[]){
      if(pendingTools.size>=500)pendingTools.delete(pendingTools.values().next().value);
      pendingTools.add(String(call.id));
    }
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
  url: () => liveEndpoint(googleLiveProvider.url(),companionEnabled()),
  createProtocol: () => guardSilentOutput(wrapGoogleProtocol(googleLiveProvider.createProtocol())),
  buildSession(args) {
    const session=googleLiveProvider.buildSession(args);
    const companion=companionEnabled();
    return {...session,
      ...(companion?{proactivity:{proactiveAudio:true}}:{}),
      systemInstruction:{...session.systemInstruction,parts:[...session.systemInstruction.parts,{text:beijingConnectionContext()},{text:liveIdentityInstructions},
        ...(companion?[{text:liveCompanionInstructions}]:[]),{text:liveLanguageInstructions}]},
      // These are short foreground operations. Gemini 3.8 otherwise defaults
      // to non-blocking tools and may confirm several times while they finish.
      realtimeInputConfig:liveInputConfig(session.realtimeInputConfig),tools:session.tools.map(tool=>({...tool,functionDeclarations:tool.functionDeclarations.map(fn=>({...fn,
        ...(['web_search','fetch_url','notes'].includes(fn.name)?{behavior:'BLOCKING'}:{}),
        parameters:liveSchema(fn.parameters)}))}))};
  },
};
