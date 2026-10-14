import {VisualState} from './visual-state.mjs';
const $=id=>document.getElementById(id),visual=new VisualState();
let socket,ready=false,frames=0,retry,level=0,gazeX=0,gazeY=0,requested=0;
const contexts=[$('eye-left'),$('eye-right')].map(c=>c.getContext('2d',{alpha:false}));
const images=contexts.map(c=>c.createImageData(240,240));
function showDemo(){document.querySelectorAll('[data-demo]').forEach(b=>{b.classList.toggle('active',visual.demo===b.dataset.demo);b.disabled=visual.actual!=='idle';});$('demo-note').textContent=visual.demo?'正在演示表情；点击恢复，或开始通话即可回到真实状态。':visual.actual==='idle'?'演示表情仅在休息时可用，通话状态优先。':'当前由实际通话状态控制眼睛。';}
document.querySelectorAll('[data-demo]').forEach(b=>b.onclick=()=>{visual.setDemo(b.dataset.demo);showDemo();});
$('demo-exit').onclick=()=>{visual.exitDemo();showDemo();};
$('pixels').onclick=()=>{const yes=$('stage').classList.toggle('pixel-view');$('pixels').setAttribute('aria-pressed',String(yes));$('pixels').textContent=yes?'返回宠物预览':'查看实际像素';$('view-caption').textContent=yes?'实际像素视图 · 每眼 240 × 240 CSS 像素 · RGB565 · 20fps 目标':'外壳为概念预览 · 两眼均由 C++ 核心绘制 · 240 × 240 / 眼';};
window.addEventListener('pikoo:state',e=>{visual.setActual(e.detail);level=0;showDemo();});
window.addEventListener('pikoo:level',e=>{level=e.detail;});
// Both eyes share a bounded gaze target. No family identity or emotion inference.
$('stage').addEventListener('pointermove',e=>{const r=$('stage').getBoundingClientRect();gazeX=Math.max(-1,Math.min(1,(e.clientX-r.left)/r.width*2-1));gazeY=Math.max(-1,Math.min(1,(e.clientY-r.top)/r.height*2-1));});
$('stage').addEventListener('pointerleave',()=>{gazeX=0;gazeY=0;});
function connect(){
  socket=new WebSocket(`ws://${location.host}/eyes`);socket.binaryType='arraybuffer';
  socket.onmessage=e=>{
    if(typeof e.data==='string'){const m=JSON.parse(e.data);ready=m.type==='eyes.ready';return;}
    if(e.data.byteLength!==230400){socket.close();return;}
    const bytes=new DataView(e.data);
    for(let side=0;side<2;side++){
      const pixels=images[side].data;
      for(let i=0;i<57600;i++){const v=bytes.getUint16((side*57600+i)*2,true),j=i*4;pixels[j]=Math.round((v>>>11)*255/31);pixels[j+1]=Math.round((v>>>5&63)*255/63);pixels[j+2]=Math.round((v&31)*255/31);pixels[j+3]=255;}
      contexts[side].putImageData(images[side],0,0);
    }
    frames++;$('graphics-warning').hidden=true;$('renderer').classList.remove('error');$('renderer').textContent=`本机 C++ 画面正常 · ${frames} 帧 · RGB565 · 20fps 目标`;
    $('screen').dataset.visualState=visual.state;
    socket.send(JSON.stringify({type:'eyes.ack'}));
  };
  socket.onclose=()=>{ready=false;$('graphics-warning').hidden=false;$('renderer').classList.add('error');$('renderer').textContent='画面进程暂不可用，语音控制仍可使用。正在重试…';retry=setTimeout(connect,3000);};
}
setInterval(()=>{if(!ready||socket?.readyState!==1||socket.bufferedAmount>1024||document.hidden)return;const now=performance.now();if(now-requested<45)return;requested=now;socket.send(JSON.stringify({state:visual.state,time_ms:now,seed:42,level:Math.max(0,Math.min(1,level)),gaze_x:gazeX,gaze_y:gazeY}));},50);
fetch('/mode').then(r=>r.json()).then(x=>{$('model-info').textContent=x.wakeModel?`${x.wakeModel.label} · ${x.wakeModel.bytes.toLocaleString()} 字节 · 本地推理`:'未启用本地唤醒，可点击唤醒';});
window.addEventListener('pagehide',()=>{clearTimeout(retry);if(socket){socket.onclose=null;socket.close();}});
connect();showDemo();
