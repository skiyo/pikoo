// Optional browser scheduling/render test. Never runs against the live endpoint.
const $=id=>document.getElementById(id);let mock=false,started=0,timer,cycles=0,cancels=0,disconnects=0,hiddenSeconds=0,lastAction=0,speakingAt=0,lastFrame=0,frameStalls=0;
const duration=1800;
fetch('/mode').then(r=>r.json()).then(x=>{mock=x.mode==='mock';$('soak').hidden=!mock;});
window.addEventListener('pikoo:state',e=>{if(e.detail==='speaking')speakingAt=performance.now();});
$('soak').onclick=()=>{
 if(!mock)return;
 if(started){finish(false);return;}
 started=Date.now();lastAction=0;$('soak-result').hidden=false;$('soak').textContent='停止本机检查';$('wake').click();window.dispatchEvent(new CustomEvent('pikoo:test-volume',{detail:0}));
 timer=setInterval(()=>{
  const elapsed=(Date.now()-started)/1000,state=$('screen').dataset.state;
  if(document.hidden)hiddenSeconds++;
  const frames=Number($('renderer').textContent.match(/(\d+) 帧/)?.[1]||0);if(frames===lastFrame&&!document.hidden)frameStalls++;lastFrame=frames;
  if(state==='listening'&&Date.now()-lastAction>=4500){cycles++;lastAction=Date.now();$('text').value='本机连续运行检查';$('form').requestSubmit();}
  if(state==='speaking'&&cycles%4===0&&performance.now()-speakingAt>450){$('cancel').click();cancels++;lastAction=Date.now();}
  if(state==='listening'&&cycles>0&&cycles%20===0&&disconnects<cycles/20){$('drop').click();disconnects++;}
  $('soak-result').textContent=`${Math.floor(elapsed)} / ${duration} 秒 · ${frames} 帧 · ${$('screen').dataset.audioChunks||0} 音频块 · ${cycles} 轮 · ${cancels} 次取消 · ${disconnects} 次断线 · 后台 ${hiddenSeconds} 秒 · 画面停顿 ${frameStalls} 秒`;
  if(elapsed>=duration)finish(true);
 },1000);
};
function finish(complete){clearInterval(timer);$('stop').click();window.dispatchEvent(new CustomEvent('pikoo:test-volume',{detail:1}));$('soak-result').textContent=(complete?'检查完成 · ':'检查停止 · ')+$('soak-result').textContent;$('soak').textContent='运行 30 分钟本机检查（静音输出）';started=0;}
