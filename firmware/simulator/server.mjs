// Local eye preview only. Agent protocol tests run the shared native C++ core.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {WebSocketServer} from 'ws';
import {attachEyes} from './eyes-stream.mjs';
const dir=path.dirname(fileURLToPath(import.meta.url));
const port=Number(process.env.PIKOO_SIM_PORT||8793),origin=`http://127.0.0.1:${port}`;
if(!Number.isInteger(port)||port<1||port>65535)throw Error('Invalid simulator port');
const assets={'/':'dualeye.html','/dualeye':'dualeye.html','/dualeye.css':'dualeye.css','/eyes.mjs':'eyes.mjs','/visual-state.mjs':'visual-state.mjs','/demo.mjs':'demo.mjs'};
const server=http.createServer((req,res)=>{
 if(req.headers.host!==`127.0.0.1:${port}`){res.writeHead(403).end();return;}
 const name=assets[req.url];if(!name){res.writeHead(404).end();return;}
 res.setHeader('Permissions-Policy','microphone=(), camera=(), autoplay=()');
 res.setHeader('Cache-Control','no-store');res.setHeader('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'");
 res.setHeader('Content-Type',name.endsWith('.html')?'text/html; charset=utf-8':name.endsWith('.css')?'text/css':'text/javascript');res.end(fs.readFileSync(path.join(dir,name)));
});
const eyes=new WebSocketServer({noServer:true,maxPayload:1024});
eyes.on('connection',ws=>attachEyes(ws,{binary:process.env.PIKOO_EYES_BINARY}));
server.on('upgrade',(req,socket,head)=>{
 if(req.url!=='/eyes'||req.headers.origin!==origin||req.headers.host!==`127.0.0.1:${port}`){socket.destroy();return;}
 eyes.handleUpgrade(req,socket,head,ws=>eyes.emit('connection',ws));
});
server.listen(port,'127.0.0.1',()=>console.log(`Pikoo eye preview: ${origin}/dualeye`));
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>{for(const ws of eyes.clients)ws.close();server.close(()=>process.exit(0));});
