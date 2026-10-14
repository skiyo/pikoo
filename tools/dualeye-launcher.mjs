import fs from 'node:fs';
import net from 'node:net';
import {spawn,execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('../',import.meta.url)),record=`${root}firmware/build-host/dualeye-process.json`,server=`${root}firmware/simulator/server.mjs`;
const identity=pid=>{try{return execFileSync('/bin/ps',['-p',String(pid),'-o','lstart=,command='],{encoding:'utf8'}).trim();}catch{return null;}};
let previous;try{previous=JSON.parse(fs.readFileSync(record));}catch{}
const owns=()=>previous&&Number.isInteger(previous.pid)&&previous.pid>0&&typeof previous.identity==='string'&&previous.identity.includes(server)&&identity(previous.pid)===previous.identity;
const open=url=>{if(process.platform==='darwin'&&process.env.PIKOO_NO_OPEN!=='1'){const p=spawn('/usr/bin/open',[url],{stdio:'ignore'});p.on('error',()=>{});}};
if(process.argv[2]==='stop'){
  if(owns()){process.kill(previous.pid,'SIGTERM');console.log('已停止本次启动的 Pikoo 双眼模拟器。');}
  else console.log('本机没有由此启动工具管理的模拟器；其他进程保持运行。');
  if(fs.existsSync(record))fs.unlinkSync(record);
}else{
  const port=Number(process.env.PIKOO_SIM_PORT||8793),url=`http://127.0.0.1:${port}/dualeye`;
  if(owns()){console.log(`模拟器已运行：${previous.url}`);open(previous.url);}
  else{
    const free=await new Promise(resolve=>{const s=net.createServer();s.once('error',()=>resolve(false));s.listen(port,'127.0.0.1',()=>s.close(()=>resolve(true)));});
    if(!free){console.error(`端口 ${port} 已占用。请关闭占用它的程序，或修改 PIKOO_SIM_PORT。没有结束其他进程。`);process.exit(1);}
    const child=spawn(process.execPath,[server],{stdio:['ignore','pipe','inherit']});
    const cleanup=()=>{try{const current=JSON.parse(fs.readFileSync(record));if(current.pid===child.pid)fs.unlinkSync(record);}catch{}};
    const timer=setTimeout(()=>{console.error('本机服务启动超时。');child.kill();process.exitCode=1;},10000);
    child.once('error',()=>{clearTimeout(timer);console.error('本机服务启动失败。');process.exitCode=1;});
    child.stdout.once('data',()=>{clearTimeout(timer);fs.writeFileSync(record,JSON.stringify({pid:child.pid,identity:identity(child.pid),url}),{mode:0o600});console.log(`打开 ${url}\n保持此窗口运行；按 Ctrl+C 或双击停止工具可结束。`);open(url);});
    child.on('exit',code=>{clearTimeout(timer);cleanup();process.exitCode=code??0;});
    for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>child.kill(signal));
  }
}
