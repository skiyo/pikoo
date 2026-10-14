import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
export const states=['boot','idle','connecting','listening','thinking','speaking','muted','offline','occupied','auth_error','happy','drowsy','curious'];
export const frameBytes=240*240*2*2;
export function attachEyes(ws,{binary=fileURLToPath(new URL('../build-host/pikoo-eyes',import.meta.url))}={}) {
  const child=spawn(binary,[],{stdio:['pipe','pipe','ignore']});
  let closed=false,busy=false,awaitingAck=false,latest=null,parts=[],length=0,deadline;
  const fail=()=>{if(closed)return;ws.close(1011,'绘制进程不可用');cleanup();};
  const cleanup=()=>{if(closed)return;closed=true;clearTimeout(deadline);child.stdin.destroy();child.kill();};
  const pump=()=>{
    if(closed||busy||awaitingAck||!latest||ws.readyState!==1)return;
    // Drop requests while the socket is congested. The browser requests the next current pose.
    if(ws.bufferedAmount>frameBytes)return;
    const line=latest;latest=null;busy=true;
    deadline=setTimeout(fail,5000);
    child.stdin.write(line);
  };
  child.on('spawn',()=>{if(ws.readyState===1)ws.send(JSON.stringify({type:'eyes.ready',width:240,height:240,format:'RGB565LE',frameBytes,fps:20}));});
  child.on('error',fail);child.on('exit',fail);child.stdin.on('error',fail);
  child.stdout.on('data',data=>{
    if(closed)return;
    if(!busy||length+data.length>frameBytes){fail();return;}
    parts.push(data);length+=data.length;
    if(length===frameBytes){
      clearTimeout(deadline);busy=false;
      if(ws.readyState===1&&ws.bufferedAmount<=frameBytes){awaitingAck=true;ws.send(Buffer.concat(parts,length));}
      parts=[];length=0;pump();
    }
  });
  ws.on('message',(data,binaryMessage)=>{
    let p;try{if(binaryMessage)throw Error();p=JSON.parse(data);if(!p||typeof p!=='object'||Array.isArray(p))throw Error();}catch{ws.close(1008);return;}
    if(p.type==='eyes.ack'){awaitingAck=false;pump();return;}
    const state=states.indexOf(p.state),time=p.time_ms,seed=p.seed??42,level=p.level??0,x=p.gaze_x??0,y=p.gaze_y??0;
    if(state<0||!Number.isFinite(time)||time<0||time>1e12||!Number.isInteger(seed)||seed<0||seed>0xffffffff||
      ![level,x,y].every(Number.isFinite)||level<0||level>1||Math.abs(x)>1||Math.abs(y)>1){ws.close(1008);return;}
    latest=`${state} ${time} ${seed} ${level} ${x} ${y}\n`;pump();
  });
  ws.on('close',cleanup);ws.on('error',cleanup);
  return child;
}
