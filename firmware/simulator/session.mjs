export function isFarewell(text) {
  const normalized=String(text||'').replace(/[\s，。！？、；：～·“”‘’,.!?;:~"']/gu,'').toLowerCase();
  return new Set(['再见','拜拜','拜','皮酷再见','再见皮酷','皮酷拜拜','拜拜皮酷','好了再见','好再见','好的再见','谢谢再见','谢谢你再见','那再见','我们下次再聊','下次再聊','结束对话','结束通话','不聊了','晚安','皮酷晚安','晚安皮酷','pikoo再见','再见pikoo','pikoo拜拜','拜拜pikoo','pikoo晚安','晚安pikoo','goodbye','byebye','goodbyepikoo','pikoogoodbye','byepikoo','pikoobye']).has(normalized);
}
export class DeviceSession {
  constructor({send,stopAudio,playAudio,stateChanged,now=()=>Date.now(),conversationId=null,newConversationId=()=>`pikoo-${globalThis.crypto.randomUUID()}`,conversationChanged=()=>{},ended=()=>{}}) {
    Object.assign(this,{send,stopAudio,playAudio,stateChanged,now,ended});
    Object.assign(this,{conversationId,newConversationId,conversationChanged});
    this.eventPrefix=`sim-${globalThis.crypto.randomUUID()}`;
    this.greetingPending=false;this.farewell=null;this.latestResponse=null;this.state='idle';this.ready=false;this.muted=false;this.announced=new Set();this.responses=new Map();this.invalid=new Set();this.epoch=0;this.lastActivity=now();this.counter=0;
  }
  event(type,fields={}) { return {type,event_id:`${this.eventPrefix}-${++this.counter}`,...fields}; }
  stateTo(s) { if(this.state!==s){this.state=s;this.stateChanged(s);} }
  wake(takeover=false,{resume=false}={}) {
    if(this.muted)return;
    if(!resume){this.greetingPending=true;this.farewell=null;this.latestResponse=null;}
    if(!this.conversationId){this.conversationId=this.newConversationId();this.conversationChanged(this.conversationId);}
    this.clear(false);this.invalid.clear();this.ready=false;this.lastActivity=this.now();this.stateTo('connecting');
    return this.event('session.hello',{protocol:{min:'7.0.0',max:'7.0.0'},client:{type:'esp32-simulator',version:'0.1.0',instance_id:'pikoo-desktop-simulator'},capabilities:['input.audio','input.text','playback.receipts','session.heartbeat','session.takeover'],locale:'zh-CN',time_zone:'Asia/Shanghai',connection:{voice_enabled:true,input_enabled:true,output_enabled:true,text_only:false,takeover}});
  }
  input(audio) { if(this.ready&&!this.muted&&!this.farewell)this.send(this.event('input_audio_buffer.append',{audio})); }
  text(text) { if(this.ready&&!this.muted&&!this.farewell) {this.lastActivity=this.now();this.send(this.event('conversation.item.create',{parts:[{type:'text',text}]}));} }
  async receive(e) {
    if(e.type==='session.ping')return this.send(this.event('session.pong',{request_event_id:e.event_id}));
    if(e.type==='voice.ready') {if(this.state==='connecting'&&!this.muted){this.ready=true;this.lastActivity=this.now();this.stateTo('listening');if(this.greetingPending){this.greetingPending=false;this.text('你好 Pikoo');}}return;}
    if(e.type==='response.started'&&typeof e.responseId==='string'){this.latestResponse={id:e.responseId,turn:e.turnId,done:false};if(this.farewell&&!this.farewell.id&&(!this.farewell.turn||!e.turnId||this.farewell.turn===e.turnId))this.farewell.id=e.responseId;if(this.ready)this.announced.add(e.responseId);else this.invalid.add(e.responseId);return;}
    if(e.type==='voice.state'&&this.ready){if(e.state==='processing')this.stateTo('thinking');else if(['idle','listening'].includes(e.state)&&!this.responses.size)this.stateTo('listening');return;}
    if(e.type==='playback.clear'){this.clear(true);if(this.ready)this.stateTo('listening');return;}
    if(e.type==='transcript.delta'||e.type==='transcript.final'){
      this.lastActivity=this.now();
      if(this.ready&&!this.farewell&&e.type==='transcript.final'&&e.role==='user'&&isFarewell(e.content)){
        const previous=e.turnId&&this.latestResponse?.turn===e.turnId?this.latestResponse:null;
        this.farewell={turn:e.turnId,id:previous?.id,done:!!previous?.done,deadline:this.now()+20000};this.tick();
      }return;}

    if(e.type==='audio.done'){const r=this.responses.get(e.responseId);if(r){r.done=true;this.finish(e.responseId);}else{this.announced.delete(e.responseId);this.invalid.add(e.responseId);this.responseDrained(e.responseId);}return;}
    if(e.type==='error') {this.lastError=e.error?.code||e.code;return;}
    if(e.type!=='audio.delta'||!this.ready||this.muted||this.invalid.has(e.responseId))return;
    if(typeof e.responseId!=='string'||e.sampleRate!==24000||typeof e.audio!=='string')return;
    const id=e.responseId,epoch=this.epoch;
    const r=this.responses.get(id)||{pending:0,done:false,started:false};
    if(r.done)return;
    this.responses.set(id,r);r.pending++;this.lastActivity=this.now();this.stateTo('speaking');
    try {
      await this.playAudio(e.audio,()=>{if(epoch===this.epoch&&!r.started){r.started=true;this.send(this.event('playback.started',{responseId:id}));}});
      if(epoch!==this.epoch)return;
      r.pending--;this.lastActivity=this.now();this.finish(id);
    } catch {if(epoch===this.epoch){this.cancel();}}
  }
  finish(id) {const r=this.responses.get(id);if(r?.done&&!r.pending){this.send(this.event('playback.ended',{responseId:id}));this.responses.delete(id);this.announced.delete(id);this.invalid.add(id);if(!this.responses.size)this.stateTo('listening');this.responseDrained(id);}}
  responseDrained(id) {if(this.latestResponse?.id===id)this.latestResponse.done=true;if(this.farewell?.id===id)this.farewell.done=true;this.tick();}
  tick() {if(this.farewell&&((this.farewell.done&&!this.responses.size)||this.now()>=this.farewell.deadline)){this.stop();this.ended('farewell');}}
  clear(receipts) {this.epoch++;this.stopAudio();for(const id of this.announced)this.invalid.add(id);this.announced.clear();for(const id of this.responses.keys()){this.invalid.add(id);if(receipts)this.send(this.event('playback.cancelled',{responseId:id,reason:'user_cancel'}));}this.responses.clear();}
  cancel() {if(!this.ready)return;this.clear(true);this.send(this.event('response.cancel'));this.ready=false;this.stateTo('connecting');this.lastActivity=this.now();}
  disconnect(code=1000) {if(this.farewell){this.stop();this.ended('farewell');return;}this.clear(false);this.ready=false;this.stateTo(this.muted?'muted':[4001,4002].includes(code)?'occupied':code===4003?'auth_error':'offline');}
  stop({endConversation=true}={}) {this.farewell=null;this.greetingPending=false;this.latestResponse=null;this.clear(true);this.ready=false;if(endConversation){this.conversationId=null;this.conversationChanged(null);}this.stateTo(this.muted?'muted':'idle');}
  setMuted(value) {this.muted=value;this.stop({endConversation:false});}
  idleDue() {return !this.farewell&&this.ready&&!this.responses.size&&this.now()-this.lastActivity>=30000;}
  sleepIfIdle() {if(!this.idleDue())return false;this.stop({endConversation:false});return true;}
}
