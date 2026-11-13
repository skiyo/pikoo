#!/usr/bin/env python3
"""Local USB assistant. Secrets are entered without echo and stored privately."""
import argparse
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys
from serial.tools import list_ports
from configure import validate,prompt_config

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--language',choices=['en','zh-CN'],default='en')
ui=parser.parse_args().language
def tr(en,zh):return zh if ui=='zh-CN' else en

root=Path(__file__).resolve().parents[1]
os.umask(0o077)
private=Path(os.environ.get('PIKOO_PRIVATE_DIR',str(Path.home()/'.config/pikoo')))
private.mkdir(parents=True,exist_ok=True);private.chmod(0o700)
ports=[p.device for p in list_ports.comports() if p.vid==0x303a and p.pid==0x1001]
if len(ports)!=1:
    raise SystemExit(tr('Connect one Pikoo board and reopen. Detected devices: ','请只连接一块 Pikoo 双眼板，再重新打开。检测到设备数量：')+str(len(ports)))
print(tr('Pikoo USB assistant\n1. Install\n2. Upgrade (preserve configuration)\n3. Status\n4. Restore backup\n5. Update configuration\n6. Volume\n7. Display orientation','Pikoo USB 助手 / USB assistant\n1. 首次安装\n2. 升级固件（保留配置）\n3. 查看状态\n4. 恢复原厂\n5. 修改 Wi-Fi 与设备配置\n6. 调整音量\n7. 调整屏幕方向'))
choice=input(tr('Choose [3]: ','选择 / Choose [3]: ')).strip() or '3'
config=private/'device-config.json'
if choice in ('1','5') and (not config.exists() or choice=='5'):
    c=prompt_config()
    validate(c);config.write_text(json.dumps(c));config.chmod(0o600)
action={'1':'install','2':'upgrade','3':'diagnose','4':'restore','5':'configure','6':'diagnose','7':'diagnose'}.get(choice)
if not action:raise SystemExit(tr('Invalid selection','无效选择'))
args=[sys.executable,str(root/'tools/device.py'),action,'--port',ports[0]]
if choice=='6':
    level=input(tr('Volume: 1 low / 2 normal / 3 higher / 4 louder [2]: ','音量：1 低 / 2 正常 / 3 提高 / 4 较大 [2]: ')).strip() or '2'
    command={'1':'volume low','2':'volume normal','3':'volume higher','4':'volume louder'}.get(level)
    if not command:raise SystemExit(tr('Invalid selection','无效选择'))
    args+=['--command',command]
    print(tr('Volume persists after restart; lower it if distorted.','音量会保存，重启保留；如出现破音请降低音量。'))
if choice=='7':
    angle=input(tr('Orientation: 90 or 270 [90]: ','方向：90 或 270 [90]: ')).strip() or '90'
    if angle not in ('90','270'):raise SystemExit(tr('Invalid orientation','无效方向'))
    args+=['--command','rotate '+angle]
if action in ('install','configure'):args+=['--config',str(config)]
if action in ('install','restore'):
    backup=private/'factory-backup'
    if not backup.exists():
        if action=='restore':raise SystemExit('Choose an existing verified backup for recovery.')
        subprocess.run([sys.executable,str(root/'tools/device.py'),'backup','--port',ports[0],'--backup',str(backup)],check=True)
    args+=['--backup',str(backup)]
subprocess.run(args,check=True)
