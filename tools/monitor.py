#!/usr/bin/env python3
"""Hold USB open for observation; opening separate terminals can reset USB JTAG.

Commands on stdin: status, wake, stop, end, mute, unmute, takeover, tone,
volume low/normal/higher. Raw diagnostics are optional and private.
"""
import argparse
import os
import json
import re
import socket
import signal
from pathlib import Path
import select
import sys
import time
import serial
from monitor_control import registry_path, ROOT

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--port')
p.add_argument('--private-log',type=Path)
p.add_argument('--headless',action='store_true')
p.add_argument('--control-socket',type=Path)
p.add_argument('--send')
a=p.parse_args()
os.umask(0o077)
commands={'status','wake test on','wake test off','wake capture','wake trace','tx hold','wake','stop','end','mute','unmute','takeover','tone','volume low','volume normal','volume higher','volume louder','volume full','rotate 90','rotate 270','companion on','companion off'}
commands.update({'eyes freeze','eyes resume'})
commands.update(f'volume {db}' for db in range(-50,1))
if a.send:
    if a.send not in commands|{'close-monitor'} or not a.control_socket:p.error('Choose a supported command and --control-socket')
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
        client.settimeout(3);client.connect(str(a.control_socket));client.sendall((a.send+'\n').encode())
        print(client.recv(8192).decode())
    raise SystemExit(0)
if not a.port:p.error('--port is required for a new monitor')
running=True
def stop(*_):
    global running
    running=False
signal.signal(signal.SIGTERM,stop)
server=None
if a.control_socket:
    # Never unlink or take over another monitor's socket.
    server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    server.bind(str(a.control_socket));a.control_socket.chmod(0o600);server.listen(2)
    registration=registry_path(a.port)
    registration.parent.mkdir(parents=True,exist_ok=True)
    registration.write_text(json.dumps({'pid':os.getpid(),'port':a.port,'project':str(ROOT),'socket':str(a.control_socket.resolve())}))
    registration.chmod(0o600)
state={'started_at':time.time(),'pid':os.getpid(),'resets_observed':0}
log=None
if a.private_log:
    a.private_log.parent.mkdir(parents=True,exist_ok=True)
    log=a.private_log.open('ab',buffering=0);a.private_log.chmod(0o600)
s=serial.Serial(port=None,baudrate=115200,timeout=.05)
s.dtr=False;s.rts=False;s.port=a.port;s.open()
print('USB monitor open. Commands: status / wake / stop / end / mute / unmute / tone. Ctrl-C closes it.',flush=True)
pending=b''
try:
    while running:
        data=s.read(8192)
        if data:
            if log:log.write(data)
            pending+=data
            while b'\n' in pending:
                line,pending=pending.split(b'\n',1)
                text=line.decode(errors='replace').strip()
                if 'diag: board=' in text:
                    fields={k:v for k,v in re.findall(r'(\w+)=([^\s]+)',text)}
                    for k,v in list(fields.items()):
                        try:fields[k]=float(v) if '.' in v else int(v)
                        except ValueError:pass
                    prior=state.get('device',{}).get('uptime_ms',0)
                    if fields.get('uptime_ms',0)<prior:state['resets_observed']+=1
                    state.update(observed_at=time.time(),device=fields)
                    if a.private_log:
                        dest=a.private_log.with_suffix('.status.json');temp=dest.with_suffix('.tmp')
                        temp.write_text(json.dumps(state,indent=2)+'\n');temp.chmod(0o600);temp.replace(dest)
                if any(tag in text for tag in ('diag:','pikoo:','wake:','Guru Meditation','assert failed','abort()','Backtrace:','Brownout')) or text.startswith('E ('):
                    print(text,flush=True)
        if len(pending)>65536:pending=b''
        if server and select.select([server],[],[],0)[0]:
            client,_=server.accept()
            with client:
                client.settimeout(1)
                try:
                    command=client.recv(128).decode().strip()
                    if command in commands:s.write((command+'\n').encode());s.flush()
                    elif command=='close-monitor':running=False
                    client.sendall(json.dumps({'queued':command,'status':state}).encode())
                except (OSError,UnicodeError):pass
        if not a.headless and select.select([sys.stdin],[],[],0)[0]:
            command=sys.stdin.readline()
            if not command:break
            command=command.strip()
            if command in commands:s.write((command+'\n').encode());s.flush()
            else:print('Unknown diagnostic command',flush=True)
except KeyboardInterrupt:
    pass
finally:
    s.close()
    if log:log.close()
    if server:
        server.close();a.control_socket.unlink(missing_ok=True)
        if registration.exists() and json.loads(registration.read_text()).get('pid')==os.getpid():
            registration.unlink()
