#!/usr/bin/env python3
"""Observe hardware diagnostics for 2h and 8h milestones; never accelerate time."""
import argparse,json,re,time
from pathlib import Path
from usb_serial import ConsoleSerial
p=argparse.ArgumentParser();p.add_argument('--port',required=True);p.add_argument('--seconds',type=int,default=28800);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
if a.seconds<1:p.error('seconds must be positive')
a.out.parent.mkdir(parents=True,exist_ok=True)
s=ConsoleSerial(port=None,baudrate=115200,timeout=.2);s.dtr=False;s.rts=False;s.port=a.port
start=time.monotonic();report={'started_unix':time.time(),'requested_seconds':a.seconds,'elapsed_seconds':0,'samples':0,'resets':0,'rx_errors':0,'tx_errors':0,'playback_gaps':0,'min_internal':None,'milestones':{},'status':'running'};previous=0;pending=b'';next_query=0
with s:
 try:
  while time.monotonic()-start<a.seconds:
   elapsed=time.monotonic()-start
   if elapsed>=next_query:s.write(b'status\n');next_query=elapsed+30
   pending+=s.read(8192)
   while b'\n' in pending:
    line,pending=pending.split(b'\n',1)
    if b'diag: board=' not in line:continue
    fields=dict(re.findall(r'(\w+)=([^\s]+)',line.decode(errors='replace')))
    uptime=int(fields.get('uptime_ms',0));report['resets']+=int(uptime<previous);previous=uptime
    report['samples']+=1;report['last']=fields
    for k in ['rx_errors','tx_errors','playback_gaps']:report[k]=max(report[k],int(fields.get(k,0)))
    v=int(fields.get('internal',0));report['min_internal']=min(report['min_internal'] or v,v)
   report['elapsed_seconds']=round(elapsed,1)
   for milestone in [7200,28800]:
    if elapsed>=milestone and str(milestone) not in report['milestones']:report['milestones'][str(milestone)]={'elapsed_seconds':round(elapsed,1),'resets':report['resets'],'rx_errors':report['rx_errors'],'tx_errors':report['tx_errors']}
   if pending and len(pending)>65536:pending=b''
   temp=a.out.with_suffix('.tmp');temp.write_text(json.dumps(report,indent=2));temp.replace(a.out)
  report['elapsed_seconds']=round(time.monotonic()-start,1)
  report['status']='passed' if report['samples'] and not any(report[k] for k in ['resets','rx_errors','tx_errors']) else 'failed'
 except BaseException as e:
  report['status']='interrupted' if isinstance(e,KeyboardInterrupt) else 'failed';report['error']=type(e).__name__;raise
 finally:a.out.write_text(json.dumps(report,indent=2));print(json.dumps({k:report[k] for k in ['status','elapsed_seconds','samples','resets','rx_errors','tx_errors']}),flush=True)
