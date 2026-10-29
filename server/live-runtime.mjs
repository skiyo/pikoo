import fs from 'node:fs';
import path from 'node:path';
import { createHash,randomUUID } from 'node:crypto';
import { OpenAiLive,liveConfig,LIVE_CAPABILITY } from './openai-live.mjs';
import { SemanticIdle,CLASSIFIER_INSTRUCTIONS,INTERACTION_SCHEMA } from './live-idle.mjs';
import { GatewayClientProtocolSession } from './node_modules/qwen-audio-agent/server/src/transport/gateway-client-protocol-session.mjs';
import { ToolCallHandler } from './node_modules/qwen-audio-agent/server/src/frontend/tools/tool-call-handler.mjs';
import { frontendTools,buildFrontendInstructions } from './node_modules/qwen-audio-agent/server/src/frontend/frontend-tools.mjs';
import { buildFrontendToolContext } from './node_modules/qwen-audio-agent/server/src/frontend/tools/frontend-tool-context.mjs';
import { TurnTranscripts } from './node_modules/qwen-audio-agent/server/src/frontend/tools/turn-transcripts.mjs';
import { optionalModuleFactories } from './node_modules/qwen-audio-agent/server/src/app/optional-modules.mjs';

export function installLiveDiagnostics() {
  const diagnostics={read:()=>({starting:true})};
  optionalModuleFactories.push(()=>({services:{},mountRoutes(app){
    app.get('/api/pikoo/live-status',(req,res)=>{
      if(req.identity?.access!=='local')return res.status(403).json({error:'Live diagnostics require local access'});
      return res.json(diagnostics.read());
    });
  }}));
  return diagnostics;
}

let installed=false;
export function installContinuousProtocol() {
  if(installed)return;installed=true;
  const receive=GatewayClientProtocolSession.prototype.receive;
  GatewayClientProtocolSession.prototype.receive=function(value) {
    if(this.mode==='pending'&&value?.type==='session.hello') {
      const supported=this.supportedCapabilities;
      this.supportedCapabilities=hello=>[...new Set([...(typeof supported==='function'?supported(hello):supported),LIVE_CAPABILITY])];
    }
    if(value?.type==='pikoo.playback.status') {
      if(!this.capabilities.includes(LIVE_CAPABILITY))return {event:null};
      const valid=typeof value.streamId==='string'&&value.streamId.length<=128&&Number.isSafeInteger(value.generation)&&value.generation>=0
        &&Number.isFinite(value.queuedMs)&&value.queuedMs>=0&&value.queuedMs<=60000
        &&Number.isFinite(value.dmaMs)&&value.dmaMs>=0&&value.dmaMs<=1000
        &&typeof value.audible==='boolean'&&typeof value.humanSpeaking==='boolean';
      return {event:valid?value:null};
    }
    return receive.call(this,value);
  };
}

// Persist a reservation BEFORE side effects. An interrupted reservation is never retried silently.
export class ToolReceipts {
  constructor(directory){this.directory=directory;fs.mkdirSync(directory,{recursive:true,mode:0o700});this.running=new Map();}
  async run(identity,call,execute) {
    const key=createHash('sha256').update(identity+'\0'+call.call_id).digest('hex'),file=path.join(this.directory,key+'.json');
    if(this.running.has(key))return this.running.get(key);
    if(fs.existsSync(file)) {const prior=JSON.parse(fs.readFileSync(file,'utf8'));return prior.status==='done'?prior.output:{error:'previous_execution_uncertain',message:'此前操作未确认，请先查询现有清单或记忆，不要重复添加。'};}
    fs.writeFileSync(file,JSON.stringify({status:'pending',name:call.name}),{mode:0o600,flag:'wx'});
    const promise=Promise.resolve().then(execute).then(output=>{
      fs.writeFileSync(file+'.tmp',JSON.stringify({status:'done',output}),{mode:0o600});fs.renameSync(file+'.tmp',file);return output;
    }).finally(()=>this.running.delete(key));
    this.running.set(key,promise);return promise;
  }
}

export function createLiveRuntime({ownerId,sessionId,send,voiceAccess,logger,initialInputSuspension},
  {services,terra,ledger,receipts,config,createTransport=options=>new OpenAiLive(options)}) {
  let closed=false,enabled=false,suspended=initialInputSuspension?.suspended===true,ready=false,sleeping=false;
  let transport=null,generation=0,sequence=0,streamId='',retry=0,retryTimer=null,persona='',greet=true;
  let fatalError='';
  let lastTelemetry=0,lastAudible=0,farewellAt=0,hasGoodbyeSpeech=false,lastOutputAt=0,taskCount=0;
  let lastAudioAt=0,latestPlayback=null;
  let memoryReplyAuthorized=true;
  const audioDiagnostics={chunks:0,maxArrivalGapMs:0};
  const segments={user:null,assistant:null};const backgroundContext=[];const outputPending=[];
  const emit=e=>{if(!closed)send(e);};
  const conversation=()=>services.conversationSync.frontendContext({ownerId,sessionId});
  const record=(role,content,id=randomUUID())=>services.conversationSync.record({ownerId,sessionId,id:`live_${id}`,role,content,source:role==='user'?'voice-user':'realtime-direct',turnId:`live_${id}`});
  const idle=new SemanticIdle({classify:async data=>JSON.parse((await terra.request({system:CLASSIFIER_INSTRUCTIONS,user:JSON.stringify(data),schema:INTERACTION_SCHEMA,purpose:'classification',timeoutMs:5000,maxOutputTokens:256})).text),
    onDirected:(items,result)=>{
      memoryReplyAuthorized=true;
      for(const item of items)record('user',item.text,item.id);
      for(const item of outputPending.splice(0))record('assistant',item.text,item.id);
      if(result.farewell){farewellAt=Date.now();hasGoodbyeSpeech=false;}
    },onDecision:result=>{if(result.label!=='directed'){memoryReplyAuthorized=false;outputPending.length=0;}},
    onError:error=>logger?.warn('pikoo.classification_failed',{code:error.code||error.name})});
  const context=()=>({frontend:buildFrontendToolContext({backendAvailability:{snapshot:()=>({configured:false})},
    disabledTools:['spawn_thinking','schedule_reminder'],frontendRetrieval:services.frontendRetrieval,memoryService:services.frontendMemory,sessionDigests:services.sessionDigests}),
    memories:services.frontendMemory?.list(ownerId,{limit:64})||[],recentMessages:conversation(),...(persona?{assistantProfile:persona}:{})});
  const toolHandler=new ToolCallHandler({ownerId,sessionId,taskManager:services.taskManager,backendRuntime:services.backendRuntime,
    backendAvailability:{snapshot:()=>({configured:false})},getTurnId:()=>'',getTurnGeneration:()=>generation,
    transcripts:new TurnTranscripts(),getFrontend:()=>null,memoryService:services.frontendMemory,notesStore:services.notesStore,
    getClientContext:()=>({locale:'zh-CN',timeZone:'Asia/Shanghai'}),frontendRetrieval:services.frontendRetrieval,
    sessionDigests:services.sessionDigests,disabledTools:['spawn_thinking','schedule_reminder'],permissionPolicy:services.permissionPolicy,
  });
  const toolOutputs=new Map();
  toolHandler.sendOutput=async(callId,output)=>{toolOutputs.set(callId,output);return output;};
  async function executeTool(call,{transportId,delegationId}) {
    const originalGeneration=generation;
    return receipts.run(`${ownerId}\0${sessionId}`,call,async()=>{
      if(closed||transport?.id!==transportId)return {error:'stale_session'};
      // Registry capability checks and original owner-scoped handlers remain authoritative.
      taskCount++;idle.task(true);emit({type:'tool.call',name:call.name,status:'running'});
      try {
        await toolHandler.handle({...call,arguments:call.arguments||'{}'},{turnId:delegationId,turnGeneration:originalGeneration});
        emit({type:'tool.call',name:call.name,status:'completed'});
        return toolOutputs.get(call.call_id)||{error:'tool_no_result'};
      } finally {taskCount--;if(!taskCount)idle.task(false);toolOutputs.delete(call.call_id);}
    });
  }
  function flushTranscript(role) {
    const segment=segments[role];if(!segment)return;segments[role]=null;
    const text=segment.text.trim();if(!text||/^(?:[<|\s]*)no\s*(?:speech|speak)[>|\s.]*$/i.test(text))return;
    emit({type:'transcript.final',role,content:text,turnId:segment.id});
    if(role==='user') {idle.input({...segment,text});backgroundContext.push({role,content:text});if(backgroundContext.length>12)backgroundContext.shift();}
    else if(segments.user||idle.pending.length||idle.inflight) {outputPending.push({...segment,text});if(outputPending.length>4)outputPending.shift();}
    else if(memoryReplyAuthorized&&idle.replyAuthorized)record(role,text,segment.id);
  }
  function transcript(role,e) {
    const previous=segments[role];
    if(previous&&Number(e.start_ms)>previous.end+800)flushTranscript(role);
    const item=segments[role]||{id:randomUUID(),text:'',end:0,at:0};
    item.text+=String(e.delta||'');item.text=item.text.slice(-8000);item.end=Number(e.end_ms)||item.end;item.at=Date.now();segments[role]=item;
    emit({type:'transcript.delta',role,content:e.delta||'',turnId:item.id});
  }
  async function stop(reason='idle') {
    if(sleeping||closed)return;sleeping=true;enabled=false;ready=false;clearTimeout(retryTimer);generation++;
    emit({type:'playback.clear',generation,reason});
    flushTranscript('user');flushTranscript('assistant');
    await transport?.close();
    voiceAccess.release();voiceAccess.changed();
    emit({type:'voice.sleep',state:'sleeping',reason,preserveContext:true});
    services.contextLearningQueue?.enqueue('memory',{ownerId,sessionId});services.contextLearningQueue?.enqueue('summary',{ownerId,sessionId});
  }
  async function connect() {
    if(closed||!enabled||suspended)return;
    ready=false;sequence=0;generation++;streamId=randomUUID();
    lastAudioAt=0;latestPlayback=null;
    emit({type:'playback.clear',generation,reason:'connecting'});
    emit({type:'voice.connection',state:'connecting',provider:'openai-live'});
    const agent=context();
    const digests=services.sessionDigests?.search({ownerId,limit:3})||[];
    const current=createTransport({config:liveConfig({tools:frontendTools(agent),history:agent.recentMessages,persona:buildFrontendInstructions(agent),memories:agent.memories,
      summary:JSON.stringify(digests.map(d=>({topics:d.topics,gist:d.gist,work:d.work}))),greeting:greet}),ledger,executeTool,
      onEvent:e=>{
        if(closed||transport!==current)return;
        if(e.type==='session.started') {
          ready=true;lastTelemetry=Date.now();retry=0;if(greet)idle.authorize();
          emit({type:'voice.ready',provider:'openai-live',inputSampleRate:16000,continuousAudio:true,streamId,generation});
          if(greet){greet=false;current.send({type:'session.commentary.append',delegation_id:null,content:'用户刚刚唤醒了你，现在用中文简短问候，然后等待。'});}
        } else if(e.type==='session.output_audio.delta'&&ready&&!sleeping) {
          const arrival=Date.now();
          if(lastAudioAt)audioDiagnostics.maxArrivalGapMs=Math.max(audioDiagnostics.maxArrivalGapMs,arrival-lastAudioAt);
          lastAudioAt=arrival;audioDiagnostics.chunks++;
          emit({type:'audio.delta',responseId:streamId,streamId,generation,sequence:sequence++,continuous:true,sampleRate:24000,audio:e.delta});
        } else if(e.type==='session.input_transcript.delta')transcript('user',e);
        else if(e.type==='session.output_transcript.delta'){lastOutputAt=Date.now();if(farewellAt)hasGoodbyeSpeech=true;transcript('assistant',e);}
      },onError:error=>{
        logger?.warn('pikoo.live_error',{code:error.code,fatal:error.fatal===true});
        if(error.fatal){fatalError=error.code;enabled=false;emit({type:'voice.connection',state:'unavailable',provider:'openai-live',message:`OpenAI: ${error.code}`});}
      },onClose:()=>{
        if(transport!==current||closed||sleeping)return;ready=false;emit({type:'playback.clear',generation:++generation,reason:'disconnected'});
        emit({type:'voice.connection',state:enabled?'reconnecting':'unavailable',provider:'openai-live'});
        if(enabled){const delay=Math.min(30000,1000*2**Math.min(retry++,5))*(0.8+Math.random()*0.4);retryTimer=setTimeout(()=>void connect(),delay);}
      }});
    transport=current;current.connect();
  }
  const ticker=setInterval(()=>{
    if(closed||!ready||sleeping)return;
    for(const role of ['user','assistant'])if(segments[role]&&Date.now()-segments[role].at>1000)flushTranscript(role);
    void idle.classifyPending([...conversation().slice(-8),...backgroundContext.slice(-4)]);
    // A lost device report must not hold an otherwise silent billed session open.
    if(Date.now()-lastTelemetry>5000)idle.playback({});
    if(idle.replyAuthorized&&!idle.playing&&!taskCount&&Date.now()-Math.max(lastOutputAt,idle.lastEffective)>5000)idle.replyAuthorized=false;
    if(farewellAt&&((hasGoodbyeSpeech&&!idle.playing&&Date.now()-lastOutputAt>2000)||Date.now()-farewellAt>20000))void stop('farewell');
    else if(idle.due())void stop('idle');
  },250);ticker.unref();
  return {
    start(){emit({type:'voice.state',state:'idle'});},
    handleClientEvent(event,{capabilities=[]}={}) {
      if(closed)return;
      if(event.type==='connect') {
        if(!capabilities.includes(LIVE_CAPABILITY)){emit({type:'voice.connection',state:'unavailable',message:'需要支持 Pikoo 连续音频的固件或模拟器。'});return;}
        if(!voiceAccess.claim().granted){voiceAccess.changed();return;}
        enabled=true;sleeping=false;fatalError='';voiceAccess.changed();void connect();
      } else if(event.type==='audio.append') {if(enabled&&ready&&!suspended&&voiceAccess.isActive())transport.append16(event.audio);}
      else if(event.type==='pikoo.playback.status') {
        if(!voiceAccess.isActive()||event.generation!==generation||event.streamId!==streamId)return;
        lastTelemetry=Date.now();if(event.audible)lastAudible=lastTelemetry;
        latestPlayback={at:lastTelemetry,queuedMs:event.queuedMs,dmaMs:event.dmaMs,audible:event.audible,humanSpeaking:event.humanSpeaking};
        idle.playback(event);emit({type:'voice.state',state:event.audible?'speaking':'listening'});
      } else if(event.type==='interrupt') {
        generation++;emit({type:'playback.clear',generation,reason:'explicit_stop'});ready=false;
        const old=transport;transport=null;
        void old?.close().then(()=>{if(!closed&&enabled)void connect();});
      } else if(['mute','sleep'].includes(event.type))void stop('client');
      else if(event.type==='input.mute')void stop('mute');
      else if(['text.message','input.message'].includes(event.type)&&ready&&voiceAccess.isActive()) {
        const text=event.text||event.parts?.filter(p=>p.type==='text').map(p=>p.text).join('')||'';
        if(/^你好\s*pikoo[。！!\s]*$/i.test(text))return; // Native startup greeting already owns this action.
        if(text){memoryReplyAuthorized=true;idle.authorize();record('user',text);transport.text(text);}
      }
    },
    status:()=>({provider:'openai-live',state:closed?'disconnected':sleeping?'sleeping':fatalError?'unavailable':ready?'connected':enabled?'connecting':'disconnected',error:fatalError||undefined,ready,connected:ready,connecting:enabled&&!ready,sleeping,generation,audio:{...audioDiagnostics},playback:latestPlayback}),
    setAssistantProfile(value){persona=String(value||'');},
    updateOutputVoice(){throw new Error('Live voice is fixed to marin');},
    handleClientDelivery(){},receiveActionResult(){return false;},updateClientPresence(state){if(state==='sleeping')void stop('client');},
    applyInputSuspension(state){suspended=state.suspended===true;if(suspended)void stop('input_suspended');},
    deactivate(){void stop('takeover');},
    async close(){if(closed)return;flushTranscript('user');flushTranscript('assistant');closed=true;enabled=false;clearInterval(ticker);clearTimeout(retryTimer);idle.close();voiceAccess.release();voiceAccess.changed();await transport?.close();services.contextLearningQueue?.enqueue('memory',{ownerId,sessionId});services.contextLearningQueue?.enqueue('summary',{ownerId,sessionId});},
  };
}

export function bindLiveRuntime(app,{terra,ledger,config,diagnostics}) {
  installContinuousProtocol();
  const runtime=app.services.frontendRuntime,originalCreate=runtime.createSession.bind(runtime),originalClose=runtime.close.bind(runtime);
  const sessions=new Set(),receipts=new ToolReceipts(path.join(config.stateDirectory,'pikoo-live-tool-receipts'));
  runtime.createSession=options=>{
    const live=createLiveRuntime(options,{services:app.services,terra,ledger,receipts,config});sessions.add(live);
    const close=live.close;live.close=async()=>{await close();sessions.delete(live);};return live;
  };
  runtime.close=async()=>{await Promise.all([...sessions].map(s=>s.close()));await originalClose();};
  if(diagnostics)diagnostics.read=()=>({provider:'openai-live',backend:'gpt-6.1-terra',sessions:[...sessions].map(s=>s.status()),usage:ledger.report()});
  return {originalCreate};
}
