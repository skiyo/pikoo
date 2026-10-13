export class DeviceSession {
  constructor({send,stopAudio,playAudio,stateChanged,now=()=>Date.now()}) {
    Object.assign(this,{send,stopAudio,playAudio,stateChanged,now});
    this.state='idle';this.ready=false;this.muted=false;this.announced=new Set();this.responses=new Map();this.invalid=new Set();this.epoch=0;this.lastActivity=now();this.counter=0;
  }
  event(type,fields={}) { return {type,event_id:`sim-${++this.counter}`,...fields}; }
  stateTo(s) { if(this.state!==s){this.state=s;this.stateChanged(s);} }
  wake(takeover=false) {
    if(this.muted)return;
    this.clear(false);this.invalid.clear();this.ready=false;this.lastActivity=this.now();this.stateTo('connecting');
    return this.event('session.hello',{protocol:{min:'7.0.0',max:'7.0.0'},client:{type:'esp32-simulator',version:'0.1.0',instance_id:'pikoo-desktop-simulator'},capabilities:['input.audio','input.text','playback.receipts','session.heartbeat','session.takeover'],locale:'zh-CN',time_zone:'Asia/Shanghai',connection:{voice_enabled:true,input_enabled:true,output_enabled:true,text_only:false,takeover}});
  }
  input(audio) { if(this.ready&&!this.muted)this.send(this.event('input_audio_buffer.append',{audio})); }
  text(text) { if(this.ready&&!this.muted) {this.lastActivity=this.now();this.send(this.event('conversation.item.create',{parts:[{type:'text',text}]}));} }
  async receive(e) {
    if(e.type==='session.ping')return this.send(this.event('session.pong',{request_event_id:e.event_id}));
    if(e.type==='voice.ready') {if(this.state==='connecting'&&!this.muted){this.ready=true;this.lastActivity=this.now();this.stateTo('listening');}return;}
    if(e.type==='response.started'&&typeof e.responseId==='string'){if(this.ready)this.announced.add(e.responseId);else this.invalid.add(e.responseId);return;}
    if(e.type==='voice.state'&&e.state==='processing'&&this.ready){this.stateTo('thinking');return;}
    if(e.type==='playback.clear'){this.clear(true);if(this.ready)this.stateTo('listening');return;}
    if(e.type==='transcript.delta'||e.type==='transcript.final'){this.lastActivity=this.now();return;}
    if(e.type==='audio.done'){const r=this.responses.get(e.responseId);if(r){r.done=true;this.finish(e.responseId);}else{this.announced.delete(e.responseId);this.invalid.add(e.responseId);}return;}
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
  finish(id) {const r=this.responses.get(id);if(r?.done&&!r.pending){this.send(this.event('playback.ended',{responseId:id}));this.responses.delete(id);this.announced.delete(id);this.invalid.add(id);if(!this.responses.size)this.stateTo('listening');}}
  clear(receipts) {this.epoch++;this.stopAudio();for(const id of this.announced)this.invalid.add(id);this.announced.clear();for(const id of this.responses.keys()){this.invalid.add(id);if(receipts)this.send(this.event('playback.cancelled',{responseId:id,reason:'user_cancel'}));}this.responses.clear();}
  cancel() {if(!this.ready)return;this.clear(true);this.send(this.event('response.cancel'));this.ready=false;this.stateTo('connecting');this.lastActivity=this.now();}
  disconnect(code=1000) {this.clear(false);this.ready=false;this.stateTo(this.muted?'muted':[4001,4002].includes(code)?'occupied':code===4003?'auth_error':'offline');}
  stop() {this.clear(true);this.ready=false;this.stateTo(this.muted?'muted':'idle');}
  setMuted(value) {this.muted=value;this.stop();}
  idleDue() {return this.ready&&!this.responses.size&&this.now()-this.lastActivity>=30000;}
}
