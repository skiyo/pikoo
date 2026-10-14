import test from 'node:test';
import assert from 'node:assert/strict';
test('page starts without microphone or voice; mute cancels a pending permission result',async()=>{
 const names=['document','window','navigator','fetch','setInterval','AudioContext','WebSocket'],old=new Map(names.map(n=>[n,Object.getOwnPropertyDescriptor(globalThis,n)]));
 const elements=new Map(),button={disabled:false};
 const element=id=>{if(!elements.has(id))elements.set(id,{textContent:'',checked:false,disabled:false,dataset:{},querySelector:()=>button});return elements.get(id);};
 let resolvePermission,requests=0,contexts=0,sockets=0,stopped=0;
 const media=new Promise(resolve=>resolvePermission=resolve);
 const mocks={document:{getElementById:element},window:new EventTarget(),navigator:{mediaDevices:{getUserMedia:()=>{requests++;return media;}}},fetch:async()=>({json:async()=>({mode:'mock',wake:false})}),setInterval:()=>0,AudioContext:class{constructor(){contexts++;}},WebSocket:class{constructor(){sockets++;}}};
 for(const n of names)Object.defineProperty(globalThis,n,{configurable:true,writable:true,value:mocks[n]});
 try{
  await import(`./app.mjs?permission-race=${Date.now()}`);assert.equal(requests,0);assert.equal(contexts,0);assert.equal(sockets,0);
  const mic=element('mic');mic.checked=true;const pending=mic.onchange();assert.equal(requests,1);
  element('mute').onclick();resolvePermission({getTracks:()=>[{stop:()=>stopped++}]});await pending;
  assert.equal(stopped,1);assert.equal(mic.checked,false);assert.equal(contexts,0);assert.equal(sockets,0);assert.equal(element('screen').dataset.state,'muted');
 }finally{for(const n of names){if(old.get(n))Object.defineProperty(globalThis,n,old.get(n));else delete globalThis[n];}}
});
test('mute during AudioWorklet loading closes capture and prevents later wake socket',async()=>{
 const names=['document','window','navigator','fetch','setInterval','AudioContext','WebSocket'],old=new Map(names.map(n=>[n,Object.getOwnPropertyDescriptor(globalThis,n)]));
 const elements=new Map(),button={disabled:false};
 const element=id=>{if(!elements.has(id))elements.set(id,{textContent:'',checked:false,disabled:false,dataset:{},querySelector:()=>button});return elements.get(id);};
 let readyModule,contexts=0,sockets=0,stopped=0,closed=0;
 const moduleLoading=new Promise(resolve=>readyModule=resolve);
 const mocks={document:{getElementById:element},window:new EventTarget(),navigator:{mediaDevices:{getUserMedia:async()=>({getTracks:()=>[{stop:()=>stopped++}]})}},fetch:async()=>({json:async()=>({mode:'mock',wake:true})}),setInterval:()=>0,AudioContext:class{constructor(){contexts++;this.audioWorklet={addModule:()=>moduleLoading};}close(){closed++;return Promise.resolve();}},WebSocket:class{constructor(){sockets++;}}};
 for(const n of names)Object.defineProperty(globalThis,n,{configurable:true,writable:true,value:mocks[n]});
 try{
  await import(`./app.mjs?worklet-race=${Date.now()}`);const mic=element('mic');mic.checked=true;const pending=mic.onchange();await Promise.resolve();assert.equal(contexts,1);
  element('mute').onclick();readyModule();await pending;
  assert.equal(stopped,1);assert.equal(closed,1);assert.equal(sockets,0);assert.equal(contexts,1);assert.equal(mic.checked,false);
 }finally{for(const n of names){if(old.get(n))Object.defineProperty(globalThis,n,old.get(n));else delete globalThis[n];}}
});
