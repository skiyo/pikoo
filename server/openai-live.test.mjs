import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { EventEmitter } from 'node:events';
import express from 'express';
import { optionalModuleFactories } from './node_modules/qwen-audio-agent/server/src/app/optional-modules.mjs';
import { Pcm16To24 } from './live-audio.mjs';
import { SemanticIdle } from './live-idle.mjs';
import { UsageLedger } from './live-usage.mjs';
import { TerraClient } from './openai-terra.mjs';
import { OpenAiLive,liveConfig,LIVE_CAPABILITY } from './openai-live.mjs';
import { ToolReceipts,installContinuousProtocol,createLiveRuntime,installLiveDiagnostics } from './live-runtime.mjs';
import { ConversationSync } from './node_modules/qwen-audio-agent/server/src/conversation/conversation-sync.mjs';
import { GatewayClientProtocolSession } from './node_modules/qwen-audio-agent/server/src/transport/gateway-client-protocol-session.mjs';
const tick=()=>new Promise(resolve=>setImmediate(resolve));
class Socket extends EventEmitter {readyState=1;bufferedAmount=0;sent=[];send(s){this.sent.push(JSON.parse(s));}terminate(){this.readyState=3;}}

test('streaming 16→24 conversion is packet independent, continuous and bounded',()=>{
 const input=Buffer.alloc(16000*2);for(let i=0;i<16000;i++)input.writeInt16LE(Math.round(18000*Math.sin(i*0.037)),i*2);
 const all=new Pcm16To24().append(input),r=new Pcm16To24(),parts=[];
 for(let n=0;n<input.length;n+=254)parts.push(r.append(input.subarray(n,n+254)));
 assert.deepEqual(Buffer.concat(parts),all);assert.equal(all.length,47998);assert.ok(r.samples.length<=1);
});
test('idle deadline permits only 15 seconds grace and genuine related playback',async()=>{
 let now=0;const idle=new SemanticIdle({now:()=>now,classify:async()=>({label:'background',farewell:false})});
 now=59000;idle.input({text:'哥哥我们去玩'});await idle.classifyPending();now=60000;assert.equal(idle.due(),true);
 idle.pending.push({text:'谁？'});assert.equal(idle.due(),false);now=75000;idle.vad=true;assert.equal(idle.due(),true);
 idle.authorize();idle.playback({audible:true});now+=90000;assert.equal(idle.due(),false);
 idle.playback({audible:false});now+=60000;assert.equal(idle.due(),false); // pending ambiguity adds bounded grace
 now+=15000;assert.equal(idle.due(),true);
});
test('classification coalesces, prevents parallel calls, ignores stale results and never calls on silence',async()=>{
 let now=0,calls=0,resolve;const kept=[];
 const idle=new SemanticIdle({now:()=>now,classify:()=>{calls++;return new Promise(r=>resolve=r);},onDirected:s=>kept.push(...s)});
 await idle.classifyPending();assert.equal(calls,0);
 idle.input({text:'旧片段'});const one=idle.classifyPending();idle.input({text:'新增片段'});await idle.classifyPending();
 resolve({label:'directed'});await one;assert.equal(kept.length,0);assert.equal(calls,1);
 now=5000;const two=idle.classifyPending();resolve({label:'directed'});await two;assert.equal(kept.length,2);assert.equal(idle.pending.length,0);
});
test('usage consumes cumulative values once, final can replace an estimate, cached reasoning not double counted',()=>{
 const ledger=new UsageLedger();ledger.live('a',30);ledger.live('a',30);ledger.live('a',45,{estimated:true});ledger.live('a',40,{final:true});ledger.live('a',60);
 assert.equal(ledger.report().liveSeconds,40);assert.equal(ledger.report().unfinalized,0);
 const usage={input_tokens:1000,input_tokens_details:{cached_tokens:500},output_tokens:100,output_tokens_details:{reasoning_tokens:70}};
 ledger.response('r','classification',usage,'gpt-6.1-terra');ledger.response('r','classification',usage,'gpt-6.1-terra');
 assert.ok(Math.abs(ledger.report().byPurpose.classification-0.001025)<1e-12);assert.equal(ledger.report().period.verified,false);
});
test('Terra uses Responses Standard low, no storage, no tools, no retries or alternate model on 429',async()=>{
 let requests=0;const client=new TerraClient({apiKey:'test',fetchImpl:async(_url,opts)=>{requests++;const body=JSON.parse(opts.body);assert.equal(body.service_tier,'default');assert.equal(body.store,false);assert.equal(body.model,'gpt-6.1-terra');assert.equal(body.tools,undefined);return new Response(JSON.stringify({error:{code:'rate_limit_exceeded',message:'sensitive'}}),{status:429});}});
 await assert.rejects(client.request({system:'classify',user:'data'}),e=>e.status===429&&!e.message.includes('sensitive'));assert.equal(requests,1);
});
test('native Live tool continuation waits for all outputs, deduplicates calls and accounts nested backend usage',async()=>{
 const socket=new Socket(),ledger=new UsageLedger();let count=0,finishTool;
 const client=new OpenAiLive({apiKey:'test',config:liveConfig(),ledger,socketFactory:()=>socket,executeTool:async()=>{count++;return new Promise(r=>finishTool=r);}}).connect();
 socket.emit('open');assert.equal(socket.sent[0].type,'session.start');assert.equal(socket.sent[0].session.audio.format.rate,24000);
 client.event({type:'session.started'});
 const event=e=>client.event({type:'response.event',delegation_id:'d',event:e});
 event({type:'response.created'});const item={type:'function_call',call_id:'c1',name:'notes',arguments:'{}'};
 event({type:'response.output_item.done',item});event({type:'response.output_item.done',item});
 event({type:'response.completed',response:{id:'r',usage:{input_tokens:1,output_tokens:2}}});await tick();assert.equal(count,1);
 assert.equal(socket.sent.filter(e=>e.type==='response.create').length,0);
 finishTool({status:'ok'});await tick();assert.equal(socket.sent.filter(e=>e.type==='response.create').length,1);
 const closing=client.close();client.event({type:'session.closed',usage:{seconds:2}});await closing;
 assert.equal(ledger.report().liveSeconds,2);assert.equal(ledger.report().unfinalized,0);
});
test('late tools cannot restart a closed Live stream and async configuration failures are fatal',async()=>{
 const socket=new Socket();let resolve,problem;
 const live=new OpenAiLive({apiKey:'test',config:liveConfig(),socketFactory:()=>socket,executeTool:()=>new Promise(r=>resolve=r),onError:e=>problem=e}).connect();
 live.event({type:'session.started'});live.event({type:'response.event',event:{type:'response.output_item.done',item:{type:'function_call',call_id:'a'}}});await tick();
 live.event({type:'response.event',event:{type:'response.completed',response:{}}});
 live.event({type:'error',error:{code:'responses_validation_failed'}});assert.equal(problem.fatal,true);resolve({status:'ok'});await tick();
 assert.equal(socket.sent.filter(e=>e.type==='response.create').length,0);live.event({type:'session.closed',usage:{seconds:1}});
});
test('recovered device audio bursts are forwarded at the capture clock without a second input queue',()=>{
 const socket=new Socket();let failures=0;
 const live=new OpenAiLive({apiKey:'test',config:liveConfig(),socketFactory:()=>socket,onError:()=>failures++}).connect();
 live.event({type:'session.started'});
 // 3.2 seconds buffered by a Wi-Fi outage, delivered in 40ms packets.
 for(let i=0;i<80;i++)live.append16(Buffer.alloc(1280));
 assert.equal(failures,0);assert.equal(live.receivedInput,true);
 assert.equal(socket.sent.filter(e=>e.type==='session.input_audio.append').length,80);
 live.event({type:'session.closed',usage:{seconds:4}});
});
test('durable tool reservation survives restart and does not repeat uncertain writes',async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'pikoo-receipts-'));let count=0;
 try {const receipts=new ToolReceipts(dir);const call={call_id:'one',name:'notes'};await receipts.run('owner:session',call,async()=>({count:++count}));
 assert.deepEqual(await new ToolReceipts(dir).run('owner:session',call,async()=>({count:++count})),{count:1});
 await assert.rejects(receipts.run('owner:session',{call_id:'two',name:'notes'},async()=>{count++;throw new Error('crash');}));
 const uncertain=await new ToolReceipts(dir).run('owner:session',{call_id:'two',name:'notes'},async()=>({count:++count}));
 assert.equal(uncertain.error,'previous_execution_uncertain');assert.equal(count,2);
 } finally{fs.rmSync(dir,{recursive:true,force:true});}
});
test('continuous capability is explicitly negotiated and malformed/unnegotiated telemetry is rejected',()=>{
 installContinuousProtocol();const session=new GatewayClientProtocolSession();
 const hello={type:'session.hello',event_id:'one',protocol:{min:'7.0.0',max:'7.0.0'},client:{type:'esp32',instance_id:'test'},capabilities:['input.audio',LIVE_CAPABILITY]};
 const result=session.receive(hello);assert.ok(result.reply.capabilities.includes(LIVE_CAPABILITY));
 assert.equal(session.receive({type:'pikoo.playback.status'}).event,null);
 assert.ok(session.receive({type:'pikoo.playback.status',streamId:'s',generation:1,queuedMs:20,dmaMs:50,audible:false,humanSpeaking:false}).event);
 assert.equal(new GatewayClientProtocolSession().receive({type:'pikoo.playback.status',streamId:'s',generation:1}).event,null);
});
test('Live runtime restores durable-source text after cancel and excludes classified background from memory',async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'pikoo-runtime-'));const sync=new ConversationSync(),transports=[],configs=[];const sent=[];
 const services={conversationSync:sync};
 const runtime=createLiveRuntime({ownerId:'o',sessionId:'s',send:e=>sent.push(e),voiceAccess:{claim:()=>({granted:true}),isActive:()=>true,release(){},changed(){}},logger:{warn(){}}},
  {services,config:{},ledger:new UsageLedger(),receipts:new ToolReceipts(dir),terra:{request:async()=>({text:'{"label":"background","farewell":false}'})},
   createTransport:options=>{configs.push(options.config);const transport={id:String(transports.length),connect(){options.onEvent({type:'session.started'});},send(){return true;},text(){},async close(){options.onClose();},event:options.onEvent};transports.push(transport);return transport;}});
 try {
  runtime.handleClientEvent({type:'connect'},{capabilities:[LIVE_CAPABILITY]});
  assert.equal(runtime.status().state,'connected');
  runtime.handleClientEvent({type:'input.message',parts:[{type:'text',text:'我正在做一艘纸船。'}]});
  assert.equal(sync.frontendContext({ownerId:'o',sessionId:'s'})[0].content,'我正在做一艘纸船。');
  runtime.handleClientEvent({type:'interrupt'});await tick();
  assert.equal(transports.length,2);assert.ok(configs[1].input.some(m=>m.role==='user'&&m.content[0].text==='我正在做一艘纸船。'));
  const audioBefore=sent.filter(e=>e.type==='audio.delta').length;
  transports[0].event({type:'session.output_audio.delta',delta:'AAA='});assert.equal(sent.filter(e=>e.type==='audio.delta').length,audioBefore);
  transports[1].event({type:'session.input_transcript.delta',delta:'哥哥把积木给我',start_ms:0,end_ms:1500});
  await new Promise(resolve=>setTimeout(resolve,1500));
  assert(!sync.frontendContext({ownerId:'o',sessionId:'s'}).some(m=>m.content.includes('积木')));
  transports[1].event({type:'session.output_transcript.delta',delta:'你们的积木真有趣',start_ms:2000,end_ms:2500});
  await new Promise(resolve=>setTimeout(resolve,1500));
  assert(!sync.frontendContext({ownerId:'o',sessionId:'s'}).some(m=>m.content.includes('积木')));
 } finally {await runtime.close();fs.rmSync(dir,{recursive:true,force:true});}
});


test('backend quota failure is fatal even when Live session.start succeeded',()=>{
 const socket=new Socket();let error;
 const live=new OpenAiLive({apiKey:'test',config:liveConfig(),socketFactory:()=>socket,onError:e=>error=e}).connect();
 live.event({type:'session.started'});
 live.event({type:'response.event',event:{type:'response.failed',response:{error:{code:'insufficient_quota'}}}});
 assert.equal(error.fatal,true);assert.equal(live.closing,true);
 live.event({type:'session.closed',usage:{seconds:1}});
});

test('Live diagnostics mount before the API catch-all and refuse remote identities',async()=>{
 const diagnostics=installLiveDiagnostics(),factory=optionalModuleFactories.pop();
 diagnostics.read=()=>({provider:'openai-live',sessions:[]});
 const app=express();app.use((req,_res,next)=>{req.identity={access:req.headers['x-test-access']||'remote'};next();});
 factory().mountRoutes(app);app.use('/api',(_req,res)=>res.sendStatus(404));
 const server=await new Promise(resolve=>{const s=app.listen(0,'127.0.0.1',()=>resolve(s));});
 try {
  const url=`http://127.0.0.1:${server.address().port}/api/pikoo/live-status`;
  assert.equal((await fetch(url)).status,403);
  const response=await fetch(url,{headers:{'x-test-access':'local'}});
  assert.equal(response.status,200);assert.equal((await response.json()).provider,'openai-live');
 }finally{await new Promise(resolve=>server.close(resolve));}
});
