import {DeviceSession} from './session.mjs';
import {loadConversation,saveConversation} from './conversation-storage.mjs';
const $=id=>document.getElementById(id);let ws,context,captureContext,stream,sources=new Set(),next=0,retry,takeover=false,retries=0,connectTimer,wakeSocket,wakeReady=false,wakeAvailable=false,continuingConversation=false;
let micGeneration=0;
let analyser,gain,outputSamples,inputLevel=0,outputLevel=0,audioChunks=0,audioEnded=0;
function outputContext(){
 if(!context||context.state==='closed'){context=new AudioContext({sampleRate:24000});analyser=context.createAnalyser();analyser.fftSize=512;outputSamples=new Float32Array(512);gain=context.createGain();analyser.connect(gain);gain.connect(context.destination);}
 return context;
}
setInterval(()=>{let rms=0;if(analyser&&sources.size){analyser.getFloatTimeDomainData(outputSamples);for(const v of outputSamples)rms+=v*v;rms=Math.sqrt(rms/outputSamples.length);}outputLevel=outputLevel*.65+Math.min(1,rms*12)*.35;const level=session.state==='speaking'?outputLevel:session.state==='listening'?inputLevel:0;$('screen').dataset.level=level.toFixed(3);window.dispatchEvent(new CustomEvent('pikoo:level',{detail:level}));inputLevel*=.88;},50);
window.addEventListener('pikoo:test-volume',e=>{if(gain)gain.gain.value=e.detail===0?0:1;});
const labels={idle:'休息中',connecting:'连接中',listening:'我在听',speaking:'正在回答',thinking:'想一想',muted:'麦克风已关闭',offline:'网络断开',occupied:'其他设备正在使用',auth_error:'请重新配对'};
function log(s){$('log').textContent=`${new Date().toLocaleTimeString()} ${s}\n`+$('log').textContent.slice(0,6000);}
let tabStorage;try{tabStorage=globalThis.sessionStorage;}catch{}
const session=new DeviceSession({conversationId:loadConversation(tabStorage),conversationChanged:id=>saveConversation(tabStorage,id),ended:reason=>{close();$('hint').textContent=reason==='unavailable'?'语音服务暂时不可用，请检查诊断':'已回到待机，唤醒后可以接着聊';},send:e=>{if(ws?.readyState===1)ws.send(JSON.stringify(e));},stopAudio:()=>{for(const s of sources){s.stop();}sources.clear();next=0;},playAudio:(b64,onStart)=>new Promise((resolve,reject)=>{
 const raw=Uint8Array.from(atob(b64),x=>x.charCodeAt(0));if(raw.length%2){reject();return;}
 if(!context){reject();return;}const pcm=new DataView(raw.buffer),buf=context.createBuffer(1,raw.length/2,24000),data=buf.getChannelData(0);
 for(let i=0;i<data.length;i++)data[i]=pcm.getInt16(i*2,true)/32768;
 if(next-context.currentTime>8){reject();return;}const source=context.createBufferSource();source.buffer=buf;source.connect(analyser);sources.add(source);
 const at=Math.max(context.currentTime,next);next=at+buf.duration;const timer=setTimeout(onStart,Math.max(0,(at-context.currentTime)*1000));
 source.onended=()=>{clearTimeout(timer);sources.delete(source);$('screen').dataset.audioEnded=String(++audioEnded);resolve();};source.start(at);$('screen').dataset.audioChunks=String(++audioChunks);
}),stateChanged:s=>{$('status').textContent=labels[s];$('screen').dataset.state=s;$('takeover').hidden=s!=='occupied';$('hint').textContent=s==='listening'?'准备好了，请说话':s==='idle'?(session.conversationId?'待机中，唤醒后可以接着聊':'点击唤醒开始'):'Pikoo 桌面模拟器';$('text').disabled=!session.ready;$('form').querySelector('button').disabled=!session.ready;$('cancel').disabled=!session.ready;window.dispatchEvent(new CustomEvent('pikoo:state',{detail:s}));log(labels[s]);}});
function connect(resume=false){clearTimeout(retry);if(session.muted)return;continuingConversation=!!session.conversationId;const hello=session.wake(takeover,{resume});saveConversation(tabStorage,session.conversationId);takeover=false;const socket=ws=new WebSocket(`ws://${location.host}/device?conversationId=${encodeURIComponent(session.conversationId)}`);
 connectTimer=setTimeout(()=>{if(socket===ws&&!session.ready)socket.close();},30000);
 socket.onopen=()=>socket.send(JSON.stringify(hello));socket.onmessage=e=>{if(socket!==ws)return;const m=JSON.parse(e.data);if(m.type.startsWith('transcript.')&&(m.content||m.text))log(m.content||m.text);session.receive(m);if(m.type==='voice.ready'){retries=0;clearTimeout(connectTimer);if(continuingConversation){$('hint').textContent='已重新连接，可以接着刚才的话题';log('重新连接本次对话；旧音频已清空');}}};
 socket.onclose=e=>{if(socket!==ws)return;session.disconnect(e.code);if(socket===ws&&!session.muted&&![4001,4002,4003].includes(e.code))retry=setTimeout(()=>connect(true),Math.min(30000,1000*2**Math.min(retries++,5))+Math.random()*500);};}
function close(){clearTimeout(retry);clearTimeout(connectTimer);const old=ws;ws=null;old?.close();}
$('wake').onclick=async()=>{await outputContext().resume();if(!session.ready){close();connect();}};
$('takeover').onclick=()=>{takeover=true;close();connect();};
$('cancel').onclick=()=>session.cancel();$('stop').onclick=()=>{session.stop();close();$('hint').textContent='已结束对话，下一次唤醒开始新话题';};
$('drop').onclick=()=>ws?.close();$('mute').onclick=()=>{session.setMuted(!session.muted);close();$('mute').textContent=session.muted?'启用麦克风':'关闭麦克风';if(session.muted)stopMic();};
$('form').onsubmit=e=>{e.preventDefault();const t=$('text').value.trim();if(t){session.text(t);$('text').value='';}};
async function stopMic(){
 micGeneration++;wakeReady=false;
 const oldWake=wakeSocket;wakeSocket=null;oldWake?.close();
 stream?.getTracks().forEach(t=>t.stop());stream=null;
 const oldCapture=captureContext;captureContext=null;
 $('mic').checked=false;inputLevel=0;
 $('notice').textContent='已停止采音。需要语音时重新勾选麦克风。';
 await oldCapture?.close().catch(()=>{});
}
function startWake(){
 const localWake=wakeSocket=new WebSocket(`ws://${location.host}/wake`);
 localWake.onmessage=e=>{
  if(localWake!==wakeSocket)return;
  const v=JSON.parse(e.data);
  if(v.type==='ready'){
   wakeReady=true;$('notice').textContent='本地唤醒已就绪，可以说“你好皮酷”。待机音频不出本机。';
   log('本地实验唤醒模型已就绪，可以说：你好皮酷');
  }
  if(v.type==='wake'&&session.state==='idle'&&!session.muted){log('检测到唤醒词');connect();}
 };
 localWake.onclose=e=>{
  if(localWake!==wakeSocket)return;
  wakeReady=false;
  $('notice').textContent=e.code===1013?'另一个页面正在使用本地唤醒。请关闭该页面，再重新勾选麦克风。':'本地唤醒已断开，可以重新勾选麦克风或点击唤醒。';
  log('本地唤醒已关闭');
 };
}
$('mic').onchange=async()=>{
 if(session.muted){$('mic').checked=false;log('请先启用麦克风，再选择采音');return;}
 if(!$('mic').checked){await stopMic();return;}
 const generation=++micGeneration;
 const current=()=>generation===micGeneration&&!session.muted&&$('mic').checked;
 try{
  const acquired=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,channelCount:1}});
  if(!current()){acquired.getTracks().forEach(t=>t.stop());return;}
  stream=acquired;
  const capture=captureContext=new AudioContext({sampleRate:16000});
  await capture.audioWorklet.addModule('/capture.js');
  if(!current())return;
  const node=new AudioWorkletNode(capture,'capture');
  node.port.onmessage=({data})=>{
   if(!current())return;
   if(!session.ready){
    if(session.state==='idle'&&wakeReady&&wakeSocket?.readyState===1&&wakeSocket.bufferedAmount<32000)wakeSocket.send(data);
    return;
   }
   const pcm=new Int16Array(data);let energy=0;
   for(const v of pcm)energy+=(v/32768)**2;
   const rms=Math.sqrt(energy/pcm.length);
   inputLevel=inputLevel*.65+Math.min(1,rms*12)*.35;
   if(rms>.02)session.lastActivity=Date.now();
   const bytes=new Uint8Array(data);let encoded='';for(const b of bytes)encoded+=String.fromCharCode(b);
   session.input(btoa(encoded));
  };
  capture.createMediaStreamSource(stream).connect(node);node.connect(capture.destination);
  await capture.resume();if(!current())return;
  await outputContext().resume();if(!current())return;
  $('notice').textContent=wakeAvailable?'正在准备本地唤醒，请稍等…':'麦克风已开启，点击唤醒开始对话。';
  if(wakeAvailable)startWake();
  log('麦克风已开启；待机音频仅送本机唤醒模型，对话就绪后才发服务器');
 }catch{
  if(generation!==micGeneration)return;
  await stopMic();$('notice').textContent='未能开启麦克风，请检查浏览器权限与输入设备。';log('未能开启麦克风');
 }
};
setInterval(()=>{session.tick();session.playbackStatus({queuedMs:Math.min(60000,Math.max(0,((next||0)-(context?.currentTime||0))*1000)),audible:outputLevel>.036,humanSpeaking:inputLevel>.12});if(session.sleepIfIdle())close();},250);
fetch('/mode').then(r=>r.json()).then(x=>{wakeAvailable=x.wake;$('notice').textContent=x.wake?'已加载实验唤醒功能，开启麦克风后说“你好皮酷”。待机录音不出本机。':'默认不采集麦克风。模拟模式只播放测试音。';$('mode').textContent=x.mode==='live'?'真实服务器 · 等待唤醒':'本地故障模拟';});
session.stateTo('idle');
$('text').disabled=true;$('form').querySelector('button').disabled=true;$('cancel').disabled=true;
window.dispatchEvent(new CustomEvent('pikoo:state',{detail:'idle'}));
window.addEventListener('pagehide',()=>{session.disconnect();close();stopMic();context?.close();});
