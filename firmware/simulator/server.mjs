import http from 'node:http';
import {createHash,randomUUID} from 'node:crypto';
import {spawn} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {WebSocketServer,WebSocket} from '../../server/node_modules/ws/wrapper.mjs';
import {attachEyes} from './eyes-stream.mjs';
import {socketRoute} from './socket-route.mjs';
const dir=path.dirname(fileURLToPath(import.meta.url));
const port=Number(process.env.PIKOO_SIM_PORT||8793),origin=`http://127.0.0.1:${port}`;
function loadConfig(){
 if(!process.env.PIKOO_SIM_CONFIG)return null;
 let value,u;try{value=JSON.parse(fs.readFileSync(process.env.PIKOO_SIM_CONFIG,'utf8'));u=new URL(value.endpoint);}catch{throw new Error('私密服务器配置无法读取或格式错误，请检查配置文件。');}
 if(u.protocol!=='wss:'||u.username||u.password)throw new Error('endpoint must be a credential-free wss URL');
 if(typeof value.token!=='string'||!value.token||/[\r\n]/.test(value.token))throw new Error('invalid device token');
 return value;
}
const config=loadConfig();
let wakeModel=null;
if(process.env.PIKOO_WAKE_PYTHON||process.env.PIKOO_WAKE_MODEL){
  if(!process.env.PIKOO_WAKE_PYTHON||!process.env.PIKOO_WAKE_MODEL)throw new Error('Local wake requires PIKOO_WAKE_PYTHON and PIKOO_WAKE_MODEL. No model weights are distributed; see docs/getting-started.md.');
  try{wakeModel=fs.readFileSync(process.env.PIKOO_WAKE_MODEL);}catch{throw new Error('Local wake model is missing or unreadable. Set PIKOO_WAKE_MODEL to an authorized local file.');}
}
const wakeInfo=wakeModel?{label:process.env.PIKOO_WAKE_LABEL||'Local wake model',bytes:wakeModel.length,sha256:createHash('sha256').update(wakeModel).digest('hex')}:null;
const assets={'/':'index.html','/app.mjs':'app.mjs','/session.mjs':'session.mjs','/conversation-storage.mjs':'conversation-storage.mjs','/capture.js':'capture.js','/style.css':'style.css','/wake-test':'wake-test.html','/wake-test.mjs':'wake-test.mjs','/wake-test.css':'wake-test.css'};
Object.assign(assets,{'/dualeye':'dualeye.html','/dualeye.css':'dualeye.css','/eyes.mjs':'eyes.mjs','/visual-state.mjs':'visual-state.mjs','/soak.mjs':'soak.mjs'});
const server=http.createServer((req,res)=>{
 if(req.headers.host!==`127.0.0.1:${port}`){res.writeHead(403).end();return;}
 if(req.url==='/mode'){res.setHeader('Content-Type','application/json');res.setHeader('Cache-Control','no-store');res.end(JSON.stringify({mode:config?'live':'mock',wake:!!process.env.PIKOO_WAKE_PYTHON,wakeModel:wakeInfo}));return;}
 const name=assets[req.url];if(!name){res.writeHead(404).end();return;}
 res.setHeader('Cache-Control','no-store');res.setHeader('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'");
 res.setHeader('Content-Type',name.endsWith('.html')?'text/html; charset=utf-8':name.endsWith('.css')?'text/css':'text/javascript');res.end(fs.readFileSync(path.join(dir,name)));
});
const sockets=new WebSocketServer({noServer:true,maxPayload:256*1024});
const wakeSockets=new WebSocketServer({noServer:true,maxPayload:4096});
const eyeSockets=new WebSocketServer({noServer:true,maxPayload:1024});
eyeSockets.on('connection',ws=>attachEyes(ws,{binary:process.env.PIKOO_EYES_BINARY}));
let wakeBusy=false;
server.on('upgrade',(req,socket,head)=>{
 const route=socketRoute(req.url,origin);
 if(!route||req.headers.origin!==origin||req.headers.host!==`127.0.0.1:${port}`){socket.destroy();return;}
 const target=route.path==='/eyes'?eyeSockets:route.path==='/wake'?wakeSockets:sockets;
 target.handleUpgrade(req,socket,head,ws=>target.emit('connection',ws,route));
});
wakeSockets.on('connection',ws=>{
 if(!process.env.PIKOO_WAKE_PYTHON||wakeBusy){ws.close(1013);return;}
 wakeBusy=true;
 const worker=spawn(process.env.PIKOO_WAKE_PYTHON,[path.resolve(dir,'../../training/wake_worker.py')],{stdio:['pipe','pipe','ignore']});
 let lines='',ready=false;
 worker.stdout.on('data',d=>{lines+=d.toString();let n;while((n=lines.indexOf('\n'))>=0){const line=lines.slice(0,n);lines=lines.slice(n+1);try{const event=JSON.parse(line);if(event.type==='ready')ready=true;if(ws.readyState===WebSocket.OPEN)ws.send(JSON.stringify(event));}catch{}}if(lines.length>8192){worker.kill();ws.close(1011);}});
 worker.on('error',()=>ws.close(1011));worker.on('exit',()=>{wakeBusy=false;ws.close();});
 worker.stdin.on('error',()=>{});
 ws.on('error',()=>worker.kill());
 ws.on('message',(data,isBinary)=>{if(!ready)return;if(!isBinary||data.length%320||data.length>4096||worker.stdin.writableLength>64000){ws.close(1009);return;}worker.stdin.write(data);});
 ws.on('close',()=>{worker.stdin.end();worker.kill();});
});
sockets.on('connection',(client,route)=>{
 let remote,timers=new Set(),seq=0,lastId='mock-0';
 const emit=e=>{if(client.readyState===WebSocket.OPEN)client.send(JSON.stringify({event_id:`mock-${++seq}`,...e}));};
 const later=(fn,ms)=>{const timer=setTimeout(()=>{timers.delete(timer);fn();},ms);timers.add(timer);};
 if(config){
   const endpoint=new URL(config.endpoint);endpoint.searchParams.set('sessionId',route?.conversationId||`sim-${randomUUID()}`);
   remote=new WebSocket(endpoint,{headers:{Authorization:`Bearer ${config.token}`,Origin:new URL(config.endpoint.replace(/^wss:/,'https:')).origin},maxPayload:256*1024,handshakeTimeout:15000});
   const pending=[];
   client.on('message',d=>{if(remote.readyState===WebSocket.OPEN)remote.send(d.toString());else if(pending.length<4)pending.push(d.toString());});
   remote.on('open',()=>pending.forEach(d=>remote.send(d)));
   remote.on('message',d=>{if(client.readyState===WebSocket.OPEN)client.send(d.toString());});
   remote.on('close',(code)=>client.close([4001,4002,4003].includes(code)?code:1011));
   remote.on('unexpected-response',(_,res)=>{client.close([401,403].includes(res.statusCode)?4003:1011);res.resume();remote.terminate();});
   remote.on('error',()=>client.close(1011));
 } else {
   const audio=()=>{const b=Buffer.alloc(4800);for(let i=0;i<2400;i++)b.writeInt16LE(Math.round(Math.sin(2*Math.PI*440*i/24000)*1200),i*2);return b.toString('base64');};
   client.on('message',d=>{let e;try{e=JSON.parse(d);}catch{return;}
     if(e.type==='session.hello'){emit({type:'session.ready',protocol_version:'7.0.0'});later(()=>emit({type:'voice.ready',inputSampleRate:16000}),150);}
     if(e.type==='conversation.item.create'){
       lastId=`response-${++seq}`;const id=lastId;emit({type:'response.started',responseId:id});
       emit({type:'transcript.final',role:'assistant',text:'这是本地模拟回答：正在验证播放、打断和状态切换。'});
       for(let i=0;i<30;i++)later(()=>emit({type:'audio.delta',sampleRate:24000,responseId:id,audio:audio()}),i*80);
       later(()=>emit({type:'audio.done',responseId:id}),2400);
     }
     // Leave the old producer running deliberately, exercising stale audio rejection.
     if(e.type==='response.cancel'){later(()=>emit({type:'voice.ready',inputSampleRate:16000}),200);}
   });
 }
 client.on('close',()=>{remote?.close();timers.forEach(clearTimeout);});
 client.on('error',()=>{remote?.terminate();timers.forEach(clearTimeout);});
});
server.listen(port,'127.0.0.1',()=>console.log(`Pikoo ${config?'live':'mock'} simulator: ${origin}`));
