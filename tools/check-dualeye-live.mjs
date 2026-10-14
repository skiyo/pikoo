// Explicit live smoke test with user-provided 16kHz mono PCM16 files; no recordings are committed.
import fs from 'node:fs';
import {WebSocket} from '../server/node_modules/ws/wrapper.mjs';
import {DeviceSession} from '../firmware/simulator/session.mjs';
const dir=process.argv[2];if(!dir)throw Error('Usage: node tools/check-dualeye-live.mjs /private/pcm-directory');
const port=Number(process.env.PIKOO_SIM_PORT||8793),origin=`http://127.0.0.1:${port}`;
if((await(await fetch(`${origin}/mode`)).json()).mode!=='live')throw Error('Requires explicit live simulator configuration');
const delay=ms=>new Promise(r=>setTimeout(r,ms));
let ws,eyes,frames=0,chunks=0,bytes=0,completed=0,clears=0,voiceReady=0,playTimers=new Map(),next=0,level=0;
const counts={},errors=[],results=[];
const s=new DeviceSession({send:e=>{if(ws?.readyState===1)ws.send(JSON.stringify(e));},stateChanged:()=>{},stopAudio:()=>{for(const [timer,resolve] of playTimers){clearTimeout(timer);resolve();}playTimers.clear();next=0;},playAudio:(b64,start)=>new Promise(resolve=>{
 const b=Buffer.from(b64,'base64');if(b.length%2)errors.push('odd PCM');chunks++;bytes+=b.length;
 let energy=0;for(let i=0;i<b.length;i+=2)energy+=(b.readInt16LE(i)/32768)**2;level=Math.min(1,Math.sqrt(energy/(b.length/2))*12);
 const at=Math.max(Date.now(),next);next=at+b.length/48;
 const begin=setTimeout(start,Math.max(0,at-Date.now()));const timer=setTimeout(()=>{clearTimeout(begin);playTimers.delete(timer);resolve();},Math.max(0,next-Date.now()));playTimers.set(timer,()=>{clearTimeout(begin);resolve();});
})});
const originalFinish=s.finish.bind(s);s.finish=id=>{const r=s.responses.get(id),done=r?.done&&!r.pending;originalFinish(id);if(done)completed++;};
async function wait(predicate,label,seconds=60){const until=Date.now()+seconds*1000;while(Date.now()<until){if(predicate())return;await delay(25);}throw Error(`Timeout: ${label}`);}
async function connect(){const hello=s.wake();ws=new WebSocket(`${origin.replace('http:','ws:')}/device?conversationId=${encodeURIComponent(s.conversationId)}`,{origin});ws.on('open',()=>ws.send(JSON.stringify(hello)));ws.on('message',d=>{const e=JSON.parse(d);counts[e.type]=(counts[e.type]||0)+1;if(e.type==='voice.ready')voiceReady++;if(e.type==='playback.clear')clears++;if(['error','voice.error'].includes(e.type))errors.push(e.code||e.error?.code||'provider error');s.receive(e);});ws.on('error',()=>errors.push('socket error'));ws.on('close',code=>s.disconnect(code));await wait(()=>s.ready,'voice ready');}
async function audio(name){const pcm=fs.readFileSync(`${dir}/${name}.pcm`);for(let i=0;i<pcm.length;i+=640){s.input(pcm.subarray(i,i+640).toString('base64'));await delay(20);}for(let i=0;i<75;i++){s.input(Buffer.alloc(640).toString('base64'));await delay(20);}}
const began=Date.now();eyes=new WebSocket(`${origin.replace('http:','ws:')}/eyes`,{origin});eyes.on('message',(_,binary)=>{if(binary){frames++;eyes.send(JSON.stringify({type:'eyes.ack'}));}});eyes.on('error',()=>errors.push('eye channel error'));
const timer=setInterval(()=>{if(eyes.readyState===1&&eyes.bufferedAmount<1024)eyes.send(JSON.stringify({state:s.state,time_ms:Date.now()-began,seed:42,level:s.state==='speaking'?level:0}));},50);
try{
 await connect();
 for(let round=1;round<=3;round++){const before=completed,oldBytes=bytes;await audio(`voice${round}`);await wait(()=>completed>before,`round ${round} drain`);results.push({test:`Chinese audio round ${round}`,ok:bytes>oldBytes,audioBytes:bytes-oldBytes});}
 let before=chunks;s.text('请讲一个很长的森林故事。');await wait(()=>chunks>before,'cancel audio');s.cancel();const after=chunks;await wait(()=>s.ready,'cancel ready');await delay(1000);results.push({test:'explicit cancel, next turn and stale audio rejection',ok:chunks===after});
 before=chunks;s.text('请继续讲一个很长的森林故事。');await wait(()=>chunks>before,'barge audio');const oldClears=clears,oldDone=completed;await audio('barge');await wait(()=>clears>oldClears,'server playback clear');await wait(()=>completed>oldDone,'interrupted new answer drain');results.push({test:'synthetic voice interruption',ok:clears>oldClears});
 ws.removeAllListeners('close');ws.close();s.disconnect(1006);await connect();results.push({test:'new connection ready after disconnect',ok:s.ready});
 let sent=0;const original=s.send;s.send=e=>{sent++;original(e);};s.setMuted(true);s.input(Buffer.alloc(640).toString('base64'));results.push({test:'mute blocks audio upload',ok:sent===0&&s.state==='muted'});s.send=original;
}catch(e){errors.push(e.message);}finally{clearInterval(timer);s.stop();ws?.removeAllListeners('close');ws?.close();eyes?.close();}
const result={durationSeconds:(Date.now()-began)/1000,results,frames,chunks,bytes,completed,clears,voiceReady,errors,eventCounts:counts,scope:'Generated Chinese PCM through live GCP; timer-based drain, no human microphone or hardware AEC'};
fs.writeFileSync(new URL('../firmware/build-host/dualeye-live.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify(result));if(errors.length||results.some(r=>!r.ok)||results.length<7)process.exitCode=1;
