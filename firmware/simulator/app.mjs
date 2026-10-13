import {DeviceSession} from './session.mjs';
const $=id=>document.getElementById(id);let ws,context,captureContext,stream,sources=new Set(),next=0,retry,takeover=false,retries=0,connectTimer,wakeSocket,wakeReady=false,wakeAvailable=false;
const labels={idle:'休息中',connecting:'连接中',listening:'我在听',speaking:'正在回答',thinking:'想一想',muted:'麦克风已关闭',offline:'网络断开',occupied:'其他设备正在使用',auth_error:'请重新配对'};
function log(s){$('log').textContent=`${new Date().toLocaleTimeString()} ${s}\n`+$('log').textContent.slice(0,6000);}
const session=new DeviceSession({send:e=>{if(ws?.readyState===1)ws.send(JSON.stringify(e));},stopAudio:()=>{for(const s of sources){s.stop();}sources.clear();next=0;},playAudio:(b64,onStart)=>new Promise((resolve,reject)=>{
 const raw=Uint8Array.from(atob(b64),x=>x.charCodeAt(0));if(raw.length%2){reject();return;}
 if(!context){reject();return;}const pcm=new DataView(raw.buffer),buf=context.createBuffer(1,raw.length/2,24000),data=buf.getChannelData(0);
 for(let i=0;i<data.length;i++)data[i]=pcm.getInt16(i*2,true)/32768;
 if(next-context.currentTime>8){reject();return;}const source=context.createBufferSource();source.buffer=buf;source.connect(context.destination);sources.add(source);
 const at=Math.max(context.currentTime,next);next=at+buf.duration;const timer=setTimeout(onStart,Math.max(0,(at-context.currentTime)*1000));
 source.onended=()=>{clearTimeout(timer);sources.delete(source);resolve();};source.start(at);
}),stateChanged:s=>{$('status').textContent=labels[s];$('screen').dataset.state=s;$('takeover').hidden=s!=='occupied';$('hint').textContent=s==='listening'?'准备好了，请说话':s==='idle'?'点击唤醒开始':'Pikoo 桌面模拟器';log(labels[s]);}});
function connect(){clearTimeout(retry);if(session.muted)return;const hello=session.wake(takeover);takeover=false;const socket=ws=new WebSocket(`ws://${location.host}/device`);
 connectTimer=setTimeout(()=>{if(socket===ws&&!session.ready)socket.close();},30000);
 socket.onopen=()=>socket.send(JSON.stringify(hello));socket.onmessage=e=>{if(socket!==ws)return;const m=JSON.parse(e.data);if(m.type.startsWith('transcript.')&&(m.content||m.text))log(m.content||m.text);session.receive(m);if(m.type==='voice.ready'){retries=0;clearTimeout(connectTimer);}};
 socket.onclose=e=>{if(socket!==ws)return;session.disconnect(e.code);if(!session.muted&&![4001,4002,4003].includes(e.code))retry=setTimeout(connect,Math.min(30000,1000*2**Math.min(retries++,5))+Math.random()*500);};}
function close(){clearTimeout(retry);clearTimeout(connectTimer);const old=ws;ws=null;old?.close();}
$('wake').onclick=async()=>{context ||=new AudioContext({sampleRate:24000});await context.resume();if(!session.ready){close();connect();}};
$('takeover').onclick=()=>{takeover=true;close();connect();};
$('cancel').onclick=()=>session.cancel();$('stop').onclick=()=>{session.stop();close();};
$('drop').onclick=()=>ws?.close();$('mute').onclick=()=>{session.setMuted(!session.muted);close();$('mute').textContent=session.muted?'启用麦克风':'关闭麦克风';if(session.muted)stopMic();};
$('form').onsubmit=e=>{e.preventDefault();const t=$('text').value.trim();if(t){session.text(t);$('text').value='';}};
async function stopMic(){wakeReady=false;wakeSocket?.close();wakeSocket=null;stream?.getTracks().forEach(t=>t.stop());stream=null;await captureContext?.close();captureContext=null;$('mic').checked=false;}
$('mic').onchange=async()=>{if(session.muted){$('mic').checked=false;log('请先启用麦克风，再选择采音');return;}if(!$('mic').checked){await stopMic();return;}try{stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,channelCount:1}});captureContext=new AudioContext({sampleRate:16000});await captureContext.audioWorklet.addModule('/capture.js');const node=new AudioWorkletNode(captureContext,'capture');node.port.onmessage=({data})=>{if(session.muted)return;if(!session.ready){if(session.state==='idle'&&wakeReady&&wakeSocket?.readyState===1&&wakeSocket.bufferedAmount<32000)wakeSocket.send(data);return;}const pcm=new Int16Array(data);let energy=0;for(const v of pcm)energy+=(v/32768)**2;if(Math.sqrt(energy/pcm.length)>.02)session.lastActivity=Date.now();const bytes=new Uint8Array(data);let s='';for(const b of bytes)s+=String.fromCharCode(b);session.input(btoa(s));};captureContext.createMediaStreamSource(stream).connect(node);node.connect(captureContext.destination);await captureContext.resume();context ||=new AudioContext({sampleRate:24000});await context.resume();if(wakeAvailable){wakeSocket=new WebSocket(`ws://${location.host}/wake`);wakeSocket.onmessage=e=>{const v=JSON.parse(e.data);if(v.type==='ready'){wakeReady=true;log('本地实验唤醒模型已就绪，可以说：你好皮酷');}if(v.type==='wake'&&session.state==='idle'&&!session.muted){log('检测到唤醒词');connect();}};wakeSocket.onclose=()=>{wakeReady=false;log('本地唤醒已关闭');};}log('麦克风已开启；待机音频仅送本机唤醒模型，对话就绪后才发服务器');}catch{await stopMic();log('未获得麦克风权限');}};
setInterval(()=>{if(session.idleDue()){session.stop();close();}},250);
fetch('/mode').then(r=>r.json()).then(x=>{wakeAvailable=x.wake;$('notice').textContent=x.wake?'已加载实验唤醒功能，开启麦克风后说“你好皮酷”。待机录音不出本机。':'默认不采集麦克风。模拟模式只播放测试音。';$('mode').textContent=x.mode==='live'?'已连接真实服务器':'本地故障模拟';});
session.stateTo('idle');
