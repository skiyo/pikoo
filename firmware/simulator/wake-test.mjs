const $=id=>document.getElementById(id);
const people={'adult-a':'成人 A（爸爸）','adult-b':'成人 B（妈妈）','child-a':'儿童 A（哥哥）','child-b':'儿童 B（弟弟）'};
const results=Object.fromEntries(Object.keys(people).map(k=>[k,{trials:[],backgroundSeconds:0,falseWakes:0}]));
let info, socket, stream, context, ready=false, starting=false, active=null, round=0, hit=false, peak=0, windowOpen=false, timer, generation=0;
function render(){
 $('results').replaceChildren(...Object.entries(results).map(([id,r])=>{const row=document.createElement('tr');
  for(const value of [people[id],r.trials.length,r.trials.filter(t=>t.detected).length,`${Math.floor(r.backgroundSeconds/60)} 分 ${Math.floor(r.backgroundSeconds%60)} 秒`,r.falseWakes]){const td=document.createElement('td');td.textContent=value;row.append(td);}return row;}));
 $('person').disabled=!!active; $('positive').disabled=$('negative').disabled=!ready||!!active;
 $('stop').disabled=!active;$('mic').disabled=starting||ready||!info;$('endmic').disabled=!stream&&!starting;
}
function stage(text,detail='',detected=false){$('stage').textContent=text;$('stage').dataset.hit=String(detected);$('hint').textContent=detail;}
function stopTest(message='这次测试已结束。'){
 clearTimeout(timer);generation++;windowOpen=false;
 if(active?.kind==='negative')results[active.person].backgroundSeconds+=(performance.now()-active.started)/1000;
 active=null;render();stage(message,'可以换下一位家庭成员，或保存当前结果。');
}
async function closeMic(message='麦克风已关闭。'){
 stopTest(message);ready=false;starting=false;
 const old=socket;socket=null;old?.close();stream?.getTracks().forEach(t=>t.stop());stream=null;
 const oldContext=context;context=null;await oldContext?.close();
 $('volume').value=0;$('meter').value=0;$('score').textContent='0.00';render();
}
function nextRound(token){
 if(token!==generation||!active)return;
 round++;hit=false;peak=0;windowOpen=true;
 stage(`第 ${round} / 20 轮：请说“你好皮酷”`,'请说一次，然后保持安静，等下一轮提示。');
 timer=setTimeout(()=>{
  if(token!==generation||!active)return;
  windowOpen=false;results[active.person].trials.push({detected:hit,peakScore:peak,at:new Date().toISOString()});render();
  stage(hit?'这一轮唤醒成功':'这一轮没有唤醒','稍等 2 秒，准备下一轮。',hit);
  timer=setTimeout(()=>{if(token!==generation)return;if(round===20)stopTest('20 轮测试完成。');else nextRound(token);},2000);
 },4000);
}
$('mic').onclick=async()=>{
 if(starting||ready)return;starting=true;render();stage('正在开启麦克风…');
 try{
  stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:false}});
  if(!starting){stream.getTracks().forEach(t=>t.stop());stream=null;return;}
  context=new AudioContext({sampleRate:16000});
  if(context.sampleRate!==16000)throw Error('采样率不支持，请改用 Chrome');
  await context.audioWorklet.addModule('/capture.js');
  const node=new AudioWorkletNode(context,'capture');context.createMediaStreamSource(stream).connect(node);node.connect(context.destination);
  node.port.onmessage=({data})=>{
   const pcm=new Int16Array(data);let energy=0;for(const x of pcm)energy+=(x/32768)**2;
   $('volume').value=Math.min(1,Math.sqrt(energy/pcm.length)*8);
   if(ready&&socket?.readyState===1){if(socket.bufferedAmount>32000){closeMic('采音处理跟不上，测试已停止，请重新开启。');return;}socket.send(data);}
  };
  await context.resume();socket=new WebSocket(`ws://${location.host}/wake`);const current=socket;
  const timeout=setTimeout(()=>{if(current===socket&&!ready)closeMic('模型启动超时，请重新开启麦克风。');},20000);
  current.onmessage=e=>{
   if(current!==socket)return;const event=JSON.parse(e.data);
   if(event.type==='ready'){
    clearTimeout(timeout);
    if(event.modelSha256!==info.sha256){closeMic('模型版本不一致，请刷新页面。');return;}
    starting=false;ready=true;render();stage('准备好了。','选择上面的测试者，再开始 20 次唤醒测试或普通聊天测试。');
   }
   if(event.type==='score'){$('score').textContent=event.score.toFixed(2);$('meter').value=event.score;if(windowOpen)peak=Math.max(peak,event.score);}
   if(event.type==='wake'){
    if(active?.kind==='positive'&&windowOpen){hit=true;stage(`第 ${round} / 20 轮：已听到！`,'这一轮不需要再说，等待下一轮。',true);}
    else if(active?.kind==='negative'){results[active.person].falseWakes++;render();stage('记录了一次误唤醒。','继续普通聊天，不要说目标唤醒词。',true);}
    else if(!active)stage('检测到“你好皮酷”。','这次不计分。点击测试按钮后才开始统计。',true);
   }
  };
  current.onclose=()=>{clearTimeout(timeout);if(current===socket)closeMic('本地模型连接已关闭，请重新开启麦克风。');};
  current.onerror=()=>{if(current===socket)closeMic('无法连接本地模型，请重新开启麦克风。');};
 }catch(error){await closeMic(error.name==='NotAllowedError'?'未获得麦克风权限，请在浏览器中允许后重试。':error.message||'无法开启麦克风。');}
};
$('positive').onclick=()=>{active={person:$('person').value,kind:'positive'};round=0;render();nextRound(++generation);};
$('negative').onclick=()=>{active={person:$('person').value,kind:'negative',started:performance.now()};render();stage('普通聊天测试进行中。','正常聊天，不说“你好皮酷”。结束时点击“结束这次测试”。');};
$('stop').onclick=()=>stopTest();$('endmic').onclick=()=>closeMic();
$('export').onclick=()=>{
 const snapshot=JSON.parse(JSON.stringify(results));
 if(active?.kind==='negative')snapshot[active.person].backgroundSeconds+=(performance.now()-active.started)/1000;
 const report={model:info,threshold:.9,environment:'desktop microphone; not ESP32 validation',createdAt:new Date().toISOString(),results:snapshot};
 const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));
 const a=document.createElement('a');a.href=url;a.download='pikoo-family-wake-test.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
document.addEventListener('visibilitychange',()=>{if(document.hidden&&active)stopTest('页面切到后台，本轮测试已暂停。请保持测试页在前台。');});
window.addEventListener('pagehide',()=>{stream?.getTracks().forEach(t=>t.stop());socket?.close();context?.close();});
fetch('/mode').then(r=>r.json()).then(mode=>{info=mode.wakeModel;if(!info||!mode.wake)throw Error('此入口没有启动唤醒模型');$('model').textContent=`当前模型：${info.label} · ${(info.bytes/1024).toFixed(1)} KiB · 版本 ${info.sha256.slice(0,8)}`;render();}).catch(error=>{$('model').textContent=error.message;$('mic').disabled=true;});
render();
