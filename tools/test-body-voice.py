import sys,time,json,re,subprocess,argparse,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from usb_serial import ConsoleSerial
p=argparse.ArgumentParser(description='Opt-in synthetic speech test using Mac speakers and the real Pikoo microphone. Uses configured voice/reasoning services.')
p.add_argument('--port',required=True);p.add_argument('--cases',type=Path,default=Path(__file__).resolve().parents[1]/'testdata/body_voice_cases.json');p.add_argument('--audio-dir',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();os.umask(0o077);a.out.parent.mkdir(parents=True,exist_ok=True)
if subprocess.check_output(['osascript','-e','output muted of (get volume settings)'],text=True).strip()=='true':raise RuntimeError('Mac output is muted; no acoustic tests started. Unmute explicitly before running.')
cases=json.loads(a.cases.read_text());out=a.out;results=[];events=[];pending=b'';status={};histories=[];original={}
for n in range(len(cases)):
 if not (a.audio_dir/(str(n)+'.aiff')).is_file() or (a.audio_dir/(str(n)+'.aiff')).stat().st_size<=4096:raise RuntimeError('Missing or empty synthetic speech file: '+str(n))

s=ConsoleSerial(port=None,baudrate=115200,timeout=.1,write_timeout=3);s.dtr=False;s.rts=False;s.port=a.port;s.open()
def raw(q):s.write((q+'\n').encode());s.flush()
def body(tool,args):raw('body '+json.dumps({'tool':tool,'arguments':args},separators=(',',':')))
def pump(seconds):
 global pending,status
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  pending+=s.read(8192)
  while b'\n' in pending:
   line,pending=pending.split(b'\n',1);text=line.decode(errors='replace').strip()
   if 'PIKOO_AGENT_SNAPSHOT ' in text:
    try:histories.append(json.loads(text.split('PIKOO_AGENT_SNAPSHOT ',1)[1]).get('history',[]))
    except ValueError:pass
   if 'diag: board=' in text:status=dict(re.findall(r'(\w+)=([^\s]+)',text))
   if any(k in text for k in ['PIKOO_BODY_RESULT ','body:','body_trace:','edge event=','backend http_status=','service_tls ']):events.append(text)
def ready():
 global status
 deadline=time.monotonic()+45;quiet_since=None;wake_sent=False
 while time.monotonic()<deadline:
  status={};raw('status');pump(.5)
  if not status:continue
  if status.get('muted')=='1':raw('unmute');pump(1);continue
  if status.get('upload')!='1':
   if status.get('state') in ['0','6'] and not wake_sent:raw('wake');wake_sent=True
   quiet_since=None;continue
  if status.get('state')=='2' and float(status.get('output','1'))<.003:
   if quiet_since is None:quiet_since=time.monotonic()
   if time.monotonic()-quiet_since>=2:return
  else:quiet_since=None
 raise RuntimeError('Voice channel never reached stable listening readiness')

try:
 body('body_get_state',{});pump(1)
 for line in reversed(events):
  if 'PIKOO_BODY_RESULT ' in line or 'body:' in line:
   try:
    tag='PIKOO_BODY_RESULT ' if 'PIKOO_BODY_RESULT ' in line else 'body:'
    value=json.loads(line.split(tag,1)[1]);
    if 'gain_db' in value and 'brightness_percent' in value:original=value;break
   except ValueError:pass
 if not original:raise RuntimeError('Could not read original body preferences; no tests started')
 for n,c in enumerate(cases):
  ready();body('body_set_audio',{'gain_db':-12});body('body_set_display',{'percent':50});pump(.5)
  start_index=len(events);started=time.monotonic();player=subprocess.Popen(['afplay','-v','1.5',str(a.audio_dir/(str(n)+'.aiff'))])
  while player.poll() is None:pump(.1)
  if player.wait()!=0:raise RuntimeError('Synthetic audio playback failed')
  requested=c['expected_calls'] if 'expected_calls' in c else [{'tool':c['tool'],'expected':c['expected']}]
  found=[None]*len(requested);receipt=None
  if not requested:pump(40)  # Observe delayed forbidden actions before accepting a negative case.
  deadline=time.monotonic()+40
  while time.monotonic()<deadline:
   pump(.2)
   for line in events[start_index:]:
    for index,wanted in enumerate(requested):
     prefix='tool='+wanted['tool']+' result='
     if 'body_trace:' in line and prefix in line:
      try:
       candidate=json.loads(line.split(prefix,1)[1])
       if candidate.get('applied') and all(candidate.get(k)==v for k,v in wanted['expected'].items()):found[index]=candidate
      except ValueError:pass
   if all(r is not None for r in found):receipt=found[0] if len(found)==1 else found
   if receipt is not None:break
  pump(7)
  call_events=[e for e in events[start_index:] if 'body_trace:' in e or 'edge event=' in e or 'backend http_status=' in e]
  writes=[e for e in call_events if 'body_trace: tool=body_' in e and 'tool=body_get_state ' not in e and '"applied":true' in e]
  result_sent=sum('tool_result_delivered=1' in e for e in call_events)>=len(requested)
  result={'index':n,'prompt':c['text'],'expected':c.get('expected',requested),'pass':receipt is not None and len(writes)==len(requested) and result_sent,'write_count':len(writes),'result_sent':result_sent,'receipt':receipt,'elapsed_seconds':round(time.monotonic()-started,2),'events':call_events}
  results.append(result);out.write_text(json.dumps(results,ensure_ascii=False,indent=2));print(json.dumps({'case':n,'pass':result['pass'],'elapsed_seconds':result['elapsed_seconds'],'receipt':receipt},ensure_ascii=False),flush=True)
  if (n+1)%3==0:
   raw('mute');pump(1);raw('agent export');pump(1);raw('unmute');pump(1)
   out.with_name(out.stem+'-history.private.json').write_text(json.dumps(histories,ensure_ascii=False,indent=2))
  # A stalled voice session is reset for the next independent case.
  if receipt is None:raw('mute');pump(1);raw('unmute');pump(1)
finally:
 raw('stop')
 if original:
  body('body_set_audio',{'gain_db':original['gain_db']});body('body_set_display',{'percent':original['brightness_percent']});pump(2)
 s.close()
print(json.dumps({'passed':sum(r['pass'] for r in results),'total':len(results)}),flush=True)

raise SystemExit(0 if len(results)==len(cases) and sum(r['pass'] for r in results)>=len(cases)*.9 else 1)
