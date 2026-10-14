// Local mock only. Exercises PCM draining and native rendering, without a microphone or remote quota.
import {spawn,execFileSync} from 'node:child_process';
import {once} from 'node:events';
import fs from 'node:fs';
import {WebSocket} from '../server/node_modules/ws/wrapper.mjs';
import {DeviceSession} from '../firmware/simulator/session.mjs';
const seconds=Number(process.argv[2]||1800),port=Number(process.env.PIKOO_STRESS_PORT||8794);
const origin=`http://127.0.0.1:${port}`,started=Date.now(),samples=[],errors=[];
let frames=0,pcmChunks=0,pcmSamples=0,cycles=0,cancels=0,rendererPid,device,eyes,lastState='idle',pending=new Map(),nextAudio=0;
const child=spawn(process.execPath,[new URL('../firmware/simulator/server.mjs',import.meta.url).pathname],{env:{...process.env,PIKOO_SIM_PORT:String(port),PIKOO_SIM_CONFIG:'',PIKOO_WAKE_PYTHON:''},stdio:['ignore','pipe','pipe']});
child.stderr.on('data',d=>errors.push(d.toString().slice(0,200)));
await Promise.race([once(child.stdout,'data'),new Promise((_,reject)=>setTimeout(()=>reject(Error('startup timeout')),5000).unref())]);
const session=new DeviceSession({send:e=>{if(device?.readyState===1)device.send(JSON.stringify(e));},stateChanged:s=>lastState=s,stopAudio:()=>{for(const [t,resolve] of pending){clearTimeout(t);resolve();}pending.clear();nextAudio=0;},playAudio:(b64,start)=>new Promise(resolve=>{
  const b=Buffer.from(b64,'base64');if(b.length%2)errors.push('odd PCM length');pcmChunks++;pcmSamples+=b.length/2;
  const at=Math.max(Date.now(),nextAudio);nextAudio=at+b.length/2/24000*1000;
  const begin=setTimeout(start,Math.max(0,at-Date.now()));const timer=setTimeout(()=>{clearTimeout(begin);pending.delete(timer);resolve();},Math.max(0,nextAudio-Date.now()));pending.set(timer,()=>{clearTimeout(begin);resolve();});
})});
function connect(){device=new WebSocket(`${origin.replace('http:','ws:')}/device`,{origin});device.on('open',()=>device.send(JSON.stringify(session.wake())));device.on('message',d=>{try{session.receive(JSON.parse(d));}catch{errors.push('device parse');}});device.on('error',()=>errors.push('device socket error'));}
connect();eyes=new WebSocket(`${origin.replace('http:','ws:')}/eyes`,{origin});eyes.on('message',(d,binary)=>{if(binary){if(d.length!==230400)errors.push('bad eye frame');frames++;eyes.send(JSON.stringify({type:'eyes.ack'}));}});eyes.on('error',()=>errors.push('eyes socket error'));
const eyeTimer=setInterval(()=>{if(eyes.readyState===1&&eyes.bufferedAmount<1024)eyes.send(JSON.stringify({state:lastState,time_ms:Date.now()-started,seed:42,level:lastState==='speaking'?.3:0}));},50);
const conversationTimer=setInterval(()=>{if(session.ready&&!session.responses.size){cycles++;session.text('本地压力测试');if(cycles%4===0)setTimeout(()=>{session.cancel();cancels++;},500);}},4000);
const sampleTimer=setInterval(()=>{
  try{const rows=execFileSync('/bin/ps',['-axo','pid=,ppid=,%cpu=,rss=,command='],{encoding:'utf8'}).trim().split('\n').map(l=>l.trim().split(/\s+/));const selected=rows.filter(r=>Number(r[0])===child.pid||Number(r[1])===child.pid||Number(r[0])===process.pid);const render=selected.find(r=>r.slice(4).join(' ').includes('build-host/pikoo-eyes'));rendererPid=render?Number(render[0]):rendererPid;samples.push({elapsed:Math.round((Date.now()-started)/1000),frames,pcmChunks,processes:selected.map(r=>({pid:Number(r[0]),cpu:Number(r[2]),rssKiB:Number(r[3])}))});}catch{errors.push('resource sample failed');}
},10000);
const finish=()=>{clearInterval(eyeTimer);clearInterval(conversationTimer);clearInterval(sampleTimer);session.stop();device?.terminate();eyes?.terminate();child.kill();};
process.on('SIGINT',()=>{finish();process.exit(130);});
await new Promise(r=>setTimeout(r,seconds*1000));
finish();
const result={kind:'local mock PCM drain + native eyes; not physical microphone or speaker verification',durationSeconds:(Date.now()-started)/1000,frames,pcmChunks,pcmSamples,cycles,cancels,rendererPid,errors,samples};
const out=new URL('../firmware/build-host/dualeye-stress.json',import.meta.url);fs.writeFileSync(out,JSON.stringify(result,null,2));console.log(JSON.stringify({...result,samples:undefined}));
if(errors.length||frames<seconds*15||pcmChunks<seconds)process.exitCode=1;
