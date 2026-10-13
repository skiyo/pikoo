import http from 'node:http';
import {spawn} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {WebSocketServer,WebSocket} from '../../server/node_modules/ws/wrapper.mjs';
const dir=path.dirname(fileURLToPath(import.meta.url));
const port=Number(process.env.PIKOO_SIM_PORT||8787),origin=`http://127.0.0.1:${port}`;
const config=process.env.PIKOO_SIM_CONFIG?JSON.parse(fs.readFileSync(process.env.PIKOO_SIM_CONFIG,'utf8')):null;
if(config){const u=new URL(config.endpoint);if(u.protocol!=='wss:'||u.username||u.password)throw new Error('endpoint must be a credential-free wss URL');if(!config.token||/[\r\n]/.test(config.token))throw new Error('invalid device token');}
const assets={'/':'index.html','/app.mjs':'app.mjs','/session.mjs':'session.mjs','/capture.js':'capture.js','/style.css':'style.css'};
const server=http.createServer((req,res)=>{
 if(req.headers.host!==`127.0.0.1:${port}`){res.writeHead(403).end();return;}
 if(req.url==='/mode'){res.setHeader('Content-Type','application/json');res.end(JSON.stringify({mode:config?'live':'mock',wake:!!process.env.PIKOO_WAKE_PYTHON}));return;}
 const name=assets[req.url];if(!name){res.writeHead(404).end();return;}
 res.setHeader('Cache-Control','no-store');res.setHeader('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'");
 res.setHeader('Content-Type',name.endsWith('.html')?'text/html; charset=utf-8':name.endsWith('.css')?'text/css':'text/javascript');res.end(fs.readFileSync(path.join(dir,name)));
});
const sockets=new WebSocketServer({noServer:true,maxPayload:256*1024});
const wakeSockets=new WebSocketServer({noServer:true,maxPayload:4096});
let wakeBusy=false;
server.on('upgrade',(req,socket,head)=>{
 if(!['/device','/wake'].includes(req.url)||req.headers.origin!==origin||req.headers.host!==`127.0.0.1:${port}`){socket.destroy();return;}
 const target=req.url==='/wake'?wakeSockets:sockets;
 target.handleUpgrade(req,socket,head,ws=>target.emit('connection',ws));
});
wakeSockets.on('connection',ws=>{
 if(!process.env.PIKOO_WAKE_PYTHON||wakeBusy){ws.close(1013);return;}
 wakeBusy=true;
 const worker=spawn(process.env.PIKOO_WAKE_PYTHON,[path.resolve(dir,'../../training/wake_worker.py')],{stdio:['pipe','pipe','ignore']});
 let lines='',ready=false;
 worker.stdout.on('data',d=>{lines+=d.toString();let n;while((n=lines.indexOf('\n'))>=0){const line=lines.slice(0,n);lines=lines.slice(n+1);try{const event=JSON.parse(line);if(event.type==='ready')ready=true;if(ws.readyState===WebSocket.OPEN)ws.send(JSON.stringify(event));}catch{}}if(lines.length>8192){worker.kill();ws.close(1011);}});
 worker.on('error',()=>ws.close(1011));worker.on('exit',()=>{wakeBusy=false;ws.close();});
 worker.stdin.on('error',()=>{});
 ws.on('message',(data,isBinary)=>{if(!ready)return;if(!isBinary||data.length%320||data.length>4096||worker.stdin.writableLength>64000){ws.close(1009);return;}worker.stdin.write(data);});
 ws.on('close',()=>{worker.stdin.end();worker.kill();});
});
sockets.on('connection',client=>{
 let remote,timers=[],seq=0,lastId='mock-0';
 const emit=e=>{if(client.readyState===WebSocket.OPEN)client.send(JSON.stringify({event_id:`mock-${++seq}`,...e}));};
 const later=(fn,ms)=>timers.push(setTimeout(fn,ms));
 if(config){
   const endpoint=new URL(config.endpoint);endpoint.searchParams.set('sessionId',`sim-${Date.now()}`);
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
});
server.listen(port,'127.0.0.1',()=>console.log(`Pikoo ${config?'live':'mock'} simulator: ${origin}`));
