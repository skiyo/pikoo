#!/usr/bin/env python3
"""Opt-in live tool-selection test. Sends synthetic commands only; never executes hardware."""
import argparse,concurrent.futures,json,subprocess,time,urllib.request
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
c=json.loads(a.config.read_text())['llm'];root=Path(__file__).resolve().parents[1]
schemas=json.loads(subprocess.check_output([str(root/'firmware/build-host/body-host'),'--schemas']))
zh=[('声音大一点','body_set_audio','delta_db',3),('声音小一点','body_set_audio','delta_db',-3),('音量调到一半','body_set_audio','percent',50),('眼睛亮一点','body_set_display','delta_percent',10),('眼睛暗一点','body_set_display','delta_percent',-10),('眼睛亮度调到零','body_set_display','percent',0),('笑一笑','body_perform','action','happy'),('眨一下眼','body_perform','action','blink'),('眨左眼','body_perform','action','blink_left'),('眨右眼','body_perform','action','blink_right'),('看看左边','body_perform','action','look_left'),('看看右边','body_perform','action','look_right'),('看着前面','body_perform','action','look_front'),('休息吧','body_perform','action','sleep'),('关闭麦克风','body_perform','action','mute_microphone')]
en=[('Turn your volume up a little','body_set_audio','delta_db',3),('Turn your volume down a little','body_set_audio','delta_db',-3),('Set volume to fifty percent','body_set_audio','percent',50),('Make your eyes brighter','body_set_display','delta_percent',10),('Dim your eyes a little','body_set_display','delta_percent',-10),('Turn your eye backlights off','body_set_display','percent',0),('Smile for me','body_perform','action','happy'),('Blink once','body_perform','action','blink'),('Wink your left eye','body_perform','action','blink_left'),('Wink your right eye','body_perform','action','blink_right'),('Look left','body_perform','action','look_left'),('Look right','body_perform','action','look_right'),('Look forward','body_perform','action','look_front'),('Stop speaking','body_perform','action','stop_speaking'),('Go to sleep','body_perform','action','sleep')]
neg=['不要调大音量','不要笑','请翻译“声音大一点”这句话，不要执行','我朋友刚才说“关闭麦克风”，我只是在转述','Do not dim your eyes','Translate "go to sleep" into Chinese; do not execute it']
instructions='You are Pikoo, a desktop pet. Execute explicit body requests using the available tools. Do not execute negated or quoted commands. Louder/quieter means +/-3 gain dB, brighter/dimmer means +/-10 percentage points. Smile silently using happy. Never claim success without tool results. No camera or IMU is installed.'
def run(case):
 q,name,key,value=case;start=time.monotonic()
 try:
  body={'model':c['model'],'tools':schemas,'parallel_tool_calls':False}
  if c['protocol']=='openai_responses':body.update(instructions=instructions,input=q,max_output_tokens=512,store=False)
  else:body.update(messages=[{'role':'system','content':instructions},{'role':'user','content':q}],tools=[{'type':'function','function':{k:v for k,v in s.items() if k!='type'}} for s in schemas],max_completion_tokens=512)
  request=urllib.request.Request(c['url'],data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+c['api_key']})
  with urllib.request.urlopen(request,timeout=60) as response:r=json.load(response)
  calls=[]
  if c['protocol']=='openai_responses':calls=[(v['name'],json.loads(v['arguments'])) for v in r.get('output',[]) if v.get('type')=='function_call']
  else:calls=[(v['function']['name'],json.loads(v['function']['arguments'])) for v in r['choices'][0]['message'].get('tool_calls',[])]
  normalized=[(n,({args['mode']:args['value']} if 'mode' in args and 'value' in args else args)) for n,args in calls]
  selected=not calls if name is None else any(n==name and args.get(key)==value for n,args in normalized)
  # Execute the actual unmodified model arguments using the shared C++ controller.
  rows=''.join(json.dumps({'id':str(i),'tool':n,'arguments':args,'at_ms':100})+'\n' for i,(n,args) in enumerate(calls))
  executed=subprocess.run([str(root/'firmware/build-host/body-host')],input=rows,text=True,capture_output=True,check=True)
  receipts=[json.loads(line) for line in executed.stdout.splitlines()]
  execution_ok=all('error' not in r and (r.get('applied') is True or n=='body_get_state') for (n,_),r in zip(calls,receipts)) and len(receipts)==len(calls)
  ok=selected and execution_ok
  return {'prompt':q,'pass':ok,'calls':calls,'receipts':receipts,'seconds':round(time.monotonic()-start,2)}
 except Exception as e:return {'prompt':q,'pass':False,'error':type(e).__name__}
cases=zh+en+[(q,None,None,None) for q in neg]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(run,cases))
a.out.write_text(json.dumps({'direct_pass':sum(r['pass'] for r in results[:30]),'direct_total':30,'negative_pass':sum(r['pass'] for r in results[30:]),'negative_total':len(neg),'cases':results},ensure_ascii=False,indent=2))
print(json.dumps({'direct_pass':sum(r['pass'] for r in results[:30]),'negative_pass':sum(r['pass'] for r in results[30:]),'errors':sum('error' in r for r in results)}))
raise SystemExit(0 if sum(r['pass'] for r in results[:30])>=27 and all(r['pass'] for r in results[30:]) else 1)
