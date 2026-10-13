#!/usr/bin/env python3
"""Flash a verified ESP-IDF build via USB without overwriting provisioned NVS."""
import argparse,json,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--port',required=True);p.add_argument('--build',type=Path,default=Path(__file__).resolve().parents[1]/'firmware/build');p.add_argument('--dry-run',action='store_true');a=p.parse_args()
build=a.build.resolve();cfg=json.loads((build/'flasher_args.json').read_text())
files=[]
for offset,name in cfg['flash_files'].items():
    f=(build/name).resolve()
    if not f.is_relative_to(build) or not f.is_file():raise SystemExit('Missing or invalid build file')
    if 0x9000<=int(offset,16)<0x19000:raise SystemExit('Refusing to overwrite device NVS')
    files.extend([offset,str(f)])
cmd=[sys.executable,'-m','esptool','--chip','esp32s3','--port',a.port,'write_flash',*cfg['write_flash_args'],*files]
if a.dry_run:print('Validated flash image paths and NVS preservation; no device accessed.')
else:subprocess.run(cmd,check=True)
