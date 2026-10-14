import test from 'node:test';
import assert from 'node:assert/strict';
import {EventEmitter,once} from 'node:events';
import {spawn} from 'node:child_process';
import net from 'node:net';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {WebSocket} from '../../server/node_modules/ws/wrapper.mjs';
import {VisualState} from './visual-state.mjs';
import {attachEyes,frameBytes} from './eyes-stream.mjs';
const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function waitFor(check){const until=Date.now()+5000;while(!check()&&Date.now()<until)await delay(10);assert(check(),'condition not reached within 5 seconds');}
class Socket extends EventEmitter{
 readyState=1;bufferedAmount=0;frames=[];messages=[];
 send(d){if(Buffer.isBuffer(d))this.frames.push(d);else this.messages.push(JSON.parse(d));}
 close(code){this.code=code;this.readyState=3;this.emit('close');}
}
const pose=(time,state='idle')=>Buffer.from(JSON.stringify({state,time_ms:time,seed:42,level:.3}));
test('speech states override demonstration; exit restores actual state',()=>{
 const v=new VisualState();assert(v.setDemo('happy'));assert.equal(v.state,'happy');v.exitDemo();assert.equal(v.state,'idle');
 v.setDemo('drowsy');v.setActual('listening');assert.equal(v.state,'listening');assert.equal(v.demo,null);assert.equal(v.setDemo('curious'),false);
 for(const s of ['thinking','speaking','connecting','muted','offline','occupied','auth_error']){v.setActual(s);v.exitDemo();assert.equal(v.state,s);}
 v.setActual('idle');assert(v.setDemo('curious'));v.exitDemo();assert.equal(v.state,'idle');
});
test('slow eye client drops old poses, receives latest frame without backlog',async()=>{
 const ws=new Socket(),child=attachEyes(ws);
 try{
  await once(child,'spawn');await delay(10);assert.equal(ws.messages[0].format,'RGB565LE');
  ws.bufferedAmount=frameBytes*2;
  for(let i=0;i<200;i++)ws.emit('message',pose(i*50),false);
  await delay(100);assert.equal(ws.frames.length,0);assert.equal(child.stdin.writableLength,0);
  ws.bufferedAmount=0;ws.emit('message',pose(10000,'curious'),false);await waitFor(()=>ws.frames.length===1);
  assert.equal(ws.frames.length,1);assert.equal(ws.frames[0].length,frameBytes);
  assert.equal(ws.frames[0].readUInt16LE(0),0);assert.equal(ws.frames[0].readUInt16LE(57600*2),0);
  for(let i=0;i<200;i++)ws.emit('message',pose(11000+i*50),false);
  await delay(100);assert.equal(ws.frames.length,1); // Browser has not acknowledged its painted frame.
  ws.emit('message',Buffer.from('{"type":"eyes.ack"}'),false);await waitFor(()=>ws.frames.length===2);assert.equal(ws.frames.length,2);
 }finally{ws.close(1000);}
});
test('render crash closes only its channel; pose validation rejects unknown state',async()=>{
 const ws=new Socket(),child=attachEyes(ws);await once(child,'spawn');child.kill();await delay(100);assert.equal(ws.code,1011);
 const bad=new Socket(),p=attachEyes(bad);await once(p,'spawn');bad.emit('message',pose(1,'execute-anything'),false);await delay(20);assert.equal(bad.code,1008);
 const nul=new Socket(),n=attachEyes(nul);await once(n,'spawn');nul.emit('message',Buffer.from('null'),false);assert.equal(nul.code,1008);
});
test('missing renderer preserves device audio and eye origin guard',async()=>{
 const reserve=net.createServer();reserve.listen(0,'127.0.0.1');await once(reserve,'listening');const port=reserve.address().port;await new Promise(r=>reserve.close(r));
 const origin=`http://127.0.0.1:${port}`;
 const child=spawn(process.execPath,[new URL('./server.mjs',import.meta.url).pathname],{env:{...process.env,PIKOO_SIM_PORT:String(port),PIKOO_SIM_CONFIG:'',PIKOO_WAKE_PYTHON:'',PIKOO_WAKE_MODEL:'',PIKOO_EYES_BINARY:'/missing/pikoo-eyes'},stdio:['ignore','pipe','pipe']});
 let eyes,device;try{
  await Promise.race([once(child.stdout,'data'),delay(5000).then(()=>{throw Error('startup timeout');})]);
  const page=await fetch(`${origin}/dualeye`);assert.equal(page.status,200);assert.match(page.headers.get('content-security-policy'),/connect-src 'self'/);
  assert.equal(await new Promise((resolve,reject)=>http.get(`${origin}/dualeye`,{headers:{Host:'evil.invalid'}},r=>{r.resume();resolve(r.statusCode);}).on('error',reject)),403);
  const bad=new WebSocket(`${origin.replace('http:','ws:')}/eyes`,{origin:'https://evil.invalid'});await once(bad,'error');
  eyes=new WebSocket(`${origin.replace('http:','ws:')}/eyes`,{origin});const [code]=await once(eyes,'close');assert.equal(code,1011);
  device=new WebSocket(`${origin.replace('http:','ws:')}/device`,{origin});await once(device,'open');const received=[];
  device.on('message',d=>{const m=JSON.parse(d);received.push(m.type);if(m.type==='voice.ready')device.send(JSON.stringify({type:'conversation.item.create'}));});
  device.send(JSON.stringify({type:'session.hello'}));await delay(500);assert(received.includes('audio.delta'));
 }finally{eyes?.terminate();device?.terminate();child.kill();}
});
test('malformed private configuration does not echo credential fragments',async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'pikoo-config-')),config=path.join(dir,'private.json');
 fs.writeFileSync(config,'{"token":"synthetic-credential-do-not-echo",bad-json}',{mode:0o600});
 const child=spawn(process.execPath,[new URL('./server.mjs',import.meta.url).pathname],{env:{...process.env,PIKOO_SIM_CONFIG:config},stdio:['ignore','pipe','pipe']});let stderr='';child.stderr.on('data',d=>stderr+=d);
 try{const [code]=await once(child,'exit');assert.notEqual(code,0);assert(!stderr.includes('synthetic-credential-do-not-echo'));assert.match(stderr,/配置无法读取或格式错误/);}finally{fs.rmSync(dir,{recursive:true});}
});
