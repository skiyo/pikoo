#!/usr/bin/env python3
"""Execute the same body tools as the Agent through the USB console."""
import argparse,json,time
from usb_serial import ConsoleSerial
p=argparse.ArgumentParser();p.add_argument('--port',required=True);p.add_argument('--id',default='',help='Optional stable call ID for retry diagnostics');p.add_argument('tool',choices=['body_get_state','body_set_audio','body_set_display','body_perform']);p.add_argument('arguments',nargs='?',default='{}');a=p.parse_args()
args=json.loads(a.arguments)
if not isinstance(args,dict):p.error('arguments must be a JSON object')
wire='body '+json.dumps({'tool':a.tool,'arguments':args,'id':a.id},separators=(',',':'))+'\n'
if len(wire.encode())>510:p.error('request too large')
s=ConsoleSerial(port=None,baudrate=115200,timeout=.2,write_timeout=3);s.dtr=False;s.rts=False;s.port=a.port
with s:
 s.reset_input_buffer();s.write(wire.encode());s.flush();end=time.monotonic()+10
 while time.monotonic()<end:
  line=s.read_until(size=8192)
  if b'PIKOO_BODY_RESULT ' in line or b'body:' in line:
   tag=b'PIKOO_BODY_RESULT ' if b'PIKOO_BODY_RESULT ' in line else b'body:'
   value=line.split(tag,1)[1].strip()
   try:r=json.loads(value)
   except ValueError:continue
   print(json.dumps(r,ensure_ascii=False,indent=2));raise SystemExit(1 if 'error' in r else 0)
raise SystemExit('No body result received. Check firmware version and close other USB monitors.')
