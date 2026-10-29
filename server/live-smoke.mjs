// Explicit isolated-Gateway smoke test. Synthetic text and silent PCM; not hardware acceptance.
import fs from 'node:fs';
import WebSocket from 'ws';
import { randomUUID } from 'node:crypto';
import { pcmRms } from './live-audio.mjs';
const origin=process.env.PIKOO_TEST_ORIGIN;
if(!origin||new URL(origin).hostname!=='127.0.0.1'||new URL(origin).port==='3101')throw new Error('Set PIKOO_TEST_ORIGIN to an isolated loopback gateway (not production 3101)');
const response=await fetch(origin+'/api/health');
const cookie=response.headers.getSetCookie().map(c=>c.split(';')[0]).join('; ');
const report={startedAt:new Date().toISOString(),events:{},transcripts:[],errors:[],tools:[],synthetic:true};
let state={},audioTimer,telemetryTimer,queryTimer,finishTimer,lastAudible=0,completed=false;
const ws=new WebSocket(origin.replace('http','ws')+'/api/realtime?sessionId=live-smoke-'+randomUUID(),{headers:{Cookie:cookie,Origin:origin}});
const send=event=>{if(ws.readyState===1)ws.send(JSON.stringify({event_id:randomUUID(),...event}));};
const finish=()=>{if(completed)return;completed=true;clearInterval(audioTimer);clearInterval(telemetryTimer);clearTimeout(queryTimer);clearTimeout(finishTimer);ws.close();
 if(process.env.PIKOO_TEST_REPORT)fs.writeFileSync(process.env.PIKOO_TEST_REPORT,JSON.stringify(report,null,2),{mode:0o600});console.log(JSON.stringify(report,null,2));};
ws.on('open',()=>send({type:'session.hello',protocol:{min:'7.0.0',max:'7.0.0'},client:{type:'test',instance_id:randomUUID()},capabilities:['input.audio','input.text','playback.receipts','session.heartbeat','pikoo.audio.continuous.v1'],locale:'zh-CN',time_zone:'Asia/Shanghai',connection:{input_enabled:true,output_enabled:true}}));
ws.on('error',e=>{report.errors.push({code:e.code||e.message});finish();});
ws.on('unexpected-response',(_,res)=>{report.errors.push({http:res.statusCode});res.resume();finish();});
ws.on('message',raw=>{
 const e=JSON.parse(raw);report.events[e.type]=(report.events[e.type]||0)+1;
 if(e.type==='session.ping')send({type:'session.pong',request_event_id:e.event_id});
 if(e.type==='voice.ready') {
  clearInterval(audioTimer);clearInterval(telemetryTimer);clearTimeout(queryTimer);
  state=e;report.provider=e.provider;report.continuous=e.continuousAudio;
  audioTimer=setInterval(()=>send({type:'input_audio_buffer.append',audio:Buffer.alloc(640).toString('base64')}),20);
  telemetryTimer=setInterval(()=>send({type:'pikoo.playback.status',streamId:state.streamId,generation:state.generation,queuedMs:0,dmaMs:0,audible:Date.now()-lastAudible<200,humanSpeaking:false}),200);
  if(process.env.PIKOO_TEST_SILENCE!=='1'&&!report.querySubmitted)queryTimer=setTimeout(()=>{report.querySubmitted=true;send({type:'conversation.item.create',parts:[{type:'text',text:process.env.PIKOO_TEST_TEXT||'请调用搜索工具查一下北京今天的天气，并读出查到的结果。如果无法查到就说明失败，不要猜。'}]});},5000);
 }
 if(e.type==='audio.delta'){if(e.generation!==state.generation)report.errors.push({code:'wrong_generation'});if(pcmRms(Buffer.from(e.audio,'base64'))>0.003)lastAudible=Date.now();}
 if(e.type==='transcript.final')report.transcripts.push({role:e.role,text:e.content});
 if(e.type==='tool.call')report.tools.push({name:e.name,status:e.status});
 if(e.type==='error')report.errors.push(e.error||{message:e.message});
 if(e.type==='voice.sleep'){report.sleep={reason:e.reason,at:new Date().toISOString(),elapsedMs:Date.now()-Date.parse(report.startedAt)};finish();}
});
finishTimer=setTimeout(()=>{send({type:'mute'});setTimeout(finish,6000);},process.env.PIKOO_TEST_SILENCE==='1'?90000:55000);
await new Promise(resolve=>ws.on('close',()=>{finish();resolve();}));
