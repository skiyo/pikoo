// Explicit live test of recent conversation restoration. No family facts or credentials are logged.
import fs from 'node:fs';
import {WebSocket} from '../server/node_modules/ws/wrapper.mjs';
import {DeviceSession} from '../firmware/simulator/session.mjs';
const port=Number(process.env.PIKOO_SIM_PORT||8793),origin=`http://127.0.0.1:${port}`;
if((await(await fetch(`${origin}/mode`)).json()).mode!=='live')throw Error('Requires live simulator');
const delay=ms=>new Promise(r=>setTimeout(r,ms));const phrase=['卡通云朵','棉花星星','饼干小船','蜂蜜月亮'][Math.floor(Math.random()*4)]+['蓝莓','杏子','菠萝','布丁','奶糖'][Math.floor(Math.random()*5)];
let ws,transcript='',ended=0,chunks=0,next=0,timers=new Map(),states=[],failure;
const s=new DeviceSession({send:e=>{if(ws?.readyState===1)ws.send(JSON.stringify(e));},stopAudio:()=>{for(const [t,r] of timers){clearTimeout(t);r();}timers.clear();next=0;},stateChanged:state=>states.push(state),playAudio:(b64,start)=>new Promise(resolve=>{
 chunks++;const bytes=Buffer.from(b64,'base64').length,at=Math.max(Date.now(),next);next=at+bytes/48;
 const begin=setTimeout(start,Math.max(0,at-Date.now())),end=setTimeout(()=>{clearTimeout(begin);timers.delete(end);resolve();},Math.max(0,next-Date.now()));timers.set(end,()=>{clearTimeout(begin);resolve();});
})});
const finish=s.finish.bind(s);s.finish=id=>{const done=s.responses.get(id)?.done&&!s.responses.get(id)?.pending;finish(id);if(done)ended++;};
async function wait(check,label){const until=Date.now()+75000;while(Date.now()<until){if(failure)throw Error(failure);if(check())return;await delay(25);}throw Error(`timeout: ${label}`);}
async function connect(){const hello=s.wake(),current=ws=new WebSocket(`${origin.replace('http:','ws:')}/device?conversationId=${encodeURIComponent(s.conversationId)}`,{origin});current.on('open',()=>current.send(JSON.stringify(hello)));current.on('message',d=>{if(current!==ws)return;const e=JSON.parse(d);if(e.type==='transcript.final'&&e.role==='assistant')transcript+=e.content||e.text||'';if(e.type==='error')failure=e.code||e.error?.code||'provider error';s.receive(e);});current.on('error',()=>failure='socket error');current.on('close',code=>{if(current===ws){s.disconnect(code);if([4001,4002,4003].includes(code))failure=`connection rejected ${code}`;}});await wait(()=>s.ready,'ready');}
const began=Date.now();let remembered=false,sameConversation=false,newConversation=false;
try{
 await connect();const id=s.conversationId;s.text(`这是只用于本次会话的临时测试，不是家庭事实，不要存为长期记忆。本次暗号是“${phrase}”。请只重复暗号确认。`);await wait(()=>ended===1,'first reply');
 const before=ws;ws=null;before.close();s.disconnect(1006);await delay(400);await connect();sameConversation=s.conversationId===id;
 transcript='';s.text('刚才本次会话的暗号是什么？请只回答暗号。');await wait(()=>ended===2,'reply after reconnect');remembered=transcript.replace(/[^\p{L}\p{N}]/gu,'').includes(phrase);
 s.stop();s.wake();newConversation=s.conversationId!==id;
}catch(e){failure=e.message;}finally{s.stop();ws?.close();}
const result={ok:remembered&&sameConversation&&newConversation&&!failure,durationSeconds:(Date.now()-began)/1000,sameConversation,remembered,newConversation,chunks,error:failure??null,scope:'New Google connection restores recent text via stable GCP sessionId; not native audio-stream resumption'};
fs.writeFileSync(new URL('../firmware/build-host/context-reconnect.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify(result));if(!result.ok)process.exitCode=1;
