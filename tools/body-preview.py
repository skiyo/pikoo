#!/usr/bin/env python3
"""Render the shared C++ body controller into a portable interactive HTML preview."""
import argparse,base64,json,struct,subprocess,zlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=Path('firmware/build-host/body-preview'));a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[1];host=root/'firmware/build-host/body-host'
def png(ppm):
 data=ppm.read_bytes().split(b'\n',3)[3];w,h=480,240
 def chunk(k,v):return struct.pack('!I',len(v))+k+v+struct.pack('!I',zlib.crc32(k+v)&0xffffffff)
 return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',w,h,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(b'\0'+data[y*w*3:(y+1)*w*3] for y in range(h))))+chunk(b'IEND',b'')
frames={}
for action in ['neutral','happy','curious','drowsy','blink','blink_left','blink_right','look_left','look_right','look_front']:
 rows=[];images=[]
 for n,t in enumerate([0,50,100,175,250,350,600,1000,2000,3100,3500]):
  frame=(a.out/f'{action}-{n}.ppm').resolve()
  if n==0:rows.append({'id':'preview','tool':'body_perform','arguments':{'action':action},'at_ms':0})
  rows.append({'at_ms':t,'frame':str(frame)})
 subprocess.run([str(host)],input=''.join(json.dumps(r)+'\n' for r in rows),text=True,check=True,capture_output=True)
 for n in range(11):
  frame=a.out/f'{action}-{n}.ppm';data=png(frame);(a.out/f'{action}-{n}.png').write_bytes(data);images.append('data:image/png;base64,'+base64.b64encode(data).decode());frame.unlink()
 frames[action]=images
html='''<!doctype html><meta charset="utf-8"><title>Pikoo 身体控制预览</title><style>body{background:#101419;color:#eee;font:18px system-ui;max-width:900px;margin:40px auto;padding:20px}button{padding:10px;margin:5px;background:#25323e;color:white;border:1px solid #597;border-radius:8px}img{width:100%;max-width:720px;image-rendering:auto}small{color:#aab}</style><h1>Pikoo 身体控制</h1><p>选择动作，预览同一套 C++ 控制器与双眼渲染器产生的画面。</p><div id="buttons"></div><h2 id="label"></h2><img id="eyes"><p><small>画面不代表真实背光、音量或硬件延迟。动作结束后恢复监听表情。</small></p><script>const frames=FRAMES;const names={neutral:'自然',happy:'笑一笑',curious:'好奇',drowsy:'困倦',blink:'眨眼',blink_left:'眨左眼',blink_right:'眨右眼',look_left:'看左边',look_right:'看右边',look_front:'看前面'};let timer;const times=[0,50,100,175,250,350,600,1000,2000,3100,3500];function play(k){clearTimeout(timer);label.textContent=names[k];let i=0;function step(){eyes.src=frames[k][i];if(i<times.length-1){let delay=times[i+1]-times[i];i++;timer=setTimeout(step,delay)}}step()}for(const k in frames){let b=document.createElement('button');b.textContent=names[k];b.onclick=()=>play(k);buttons.appendChild(b)}play('happy');</script>'''.replace('FRAMES',json.dumps(frames));(a.out/'index.html').write_text(html);print(a.out/'index.html')
