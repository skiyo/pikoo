import test from 'node:test';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import net from 'node:net';
import {WebSocket} from '../../server/node_modules/ws/wrapper.mjs';
import {DeviceSession} from './session.mjs';
const delay=ms=>new Promise(r=>setTimeout(r,ms));
test('real local WebSocket: origin guard and late audio after cancellation',async()=>{
 const reserve=net.createServer();reserve.listen(0,'127.0.0.1');await once(reserve,'listening');const port=reserve.address().port;await new Promise(r=>reserve.close(r));
 const child=spawn(process.execPath,[new URL('./server.mjs',import.meta.url).pathname],{env:{...process.env,PIKOO_SIM_PORT:String(port),PIKOO_SIM_CONFIG:'',PIKOO_WAKE_PYTHON:'',PIKOO_WAKE_MODEL:''},stdio:['ignore','pipe','pipe']});
 let ws;
 try{
  await Promise.race([once(child.stdout,'data'),delay(5000).then(()=>{throw Error('mock startup timeout')})]);
  assert.equal((await fetch(`http://127.0.0.1:${port}/mode`)).status,200);
  const bad=new WebSocket(`ws://127.0.0.1:${port}/device`,{origin:'https://untrusted.invalid'});await once(bad,'error');
  const oversized=new WebSocket(`ws://127.0.0.1:${port}/device`,{origin:`http://127.0.0.1:${port}`});
  await once(oversized,'open');const oversizedClosed=once(oversized,'close');oversized.send(Buffer.alloc(256*1024+1));
  assert.equal((await oversizedClosed)[0],1009);assert.equal((await fetch(`http://127.0.0.1:${port}/mode`)).status,200);
  let played=0,cancelled=false,afterCancel=0,oldId='',late=0;
  ws=new WebSocket(`ws://127.0.0.1:${port}/device`,{origin:`http://127.0.0.1:${port}`});
  const s=new DeviceSession({send:e=>ws.send(JSON.stringify(e)),stopAudio:()=>{},stateChanged:()=>{},playAudio:async(_,start)=>{played++;start();await delay(100);}});
  ws.on('open',()=>ws.send(JSON.stringify(s.wake())));
  ws.on('message',raw=>{const e=JSON.parse(raw);if(cancelled&&e.type==='audio.delta'&&e.responseId===oldId)late++;
   s.receive(e);
   if(e.type==='audio.delta'&&!cancelled){oldId=e.responseId;cancelled=true;s.cancel();afterCancel=played;}
  });
  const until=Date.now()+5000;while(!cancelled&&Date.now()<until)await delay(20);
  assert.ok(cancelled);await delay(2700);assert.ok(late>0);assert.equal(played,afterCancel);assert.equal(s.state,'listening');
 }finally{ws?.terminate();child.kill();}
});
