#!/usr/bin/env python3
"""Create a private NVS image and optionally provision via USB. Run in ESP-IDF env."""
import argparse,csv,getpass,json,os,subprocess,sys,tempfile
from pathlib import Path
from urllib.parse import urlsplit

def validate(c):
    for key in ('ssid','password','endpoint','token'):
        if not isinstance(c.get(key),str) or '\0' in c[key]:raise ValueError('Missing/invalid '+key)
    if not 1<=len(c['ssid'].encode())<=32:raise ValueError('SSID must fit 32 UTF-8 bytes')
    if c['password'] and not 8<=len(c['password'].encode())<=63:raise ValueError('Wi-Fi password must be 8..63 bytes, or empty for an open network')
    u=urlsplit(c['endpoint'])
    if u.scheme!='wss' or not u.hostname or u.username or u.password or u.fragment or u.path!='/api/realtime':raise ValueError('Use wss://HOST/api/realtime without credentials or fragments')
    if u.query:raise ValueError('Device firmware generates the session ID; omit query parameters')
    if not 1<=len(c['token'])<=2048 or any(x.isspace() for x in c['token']):raise ValueError('Invalid device credential')
    return c

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path);p.add_argument('--output',type=Path,default=Path('config.nvs.bin'));p.add_argument('--port');p.add_argument('--dry-run',action='store_true');a=p.parse_args();os.umask(0o077)
    if a.config:c=json.loads(a.config.read_text())
    else:c={'ssid':input('2.4GHz Wi-Fi name: '),'password':getpass.getpass('Wi-Fi password: '),'endpoint':input('Device WSS endpoint: '),'token':getpass.getpass('Device token: ')}
    validate(c)
    if a.dry_run:print('Configuration is valid; no credential values displayed or written.');return
    idf=Path(os.environ.get('IDF_PATH',''))
    generator=idf/'components/nvs_flash/nvs_partition_generator/nvs_partition_gen.py'
    if not generator.is_file():raise SystemExit('Activate ESP-IDF 5.5.5 before provisioning')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pikoo-config-') as tmp:
        source=Path(tmp)/'nvs.csv'
        with source.open('w',newline='') as f:
            w=csv.writer(f);w.writerow(['key','type','encoding','value']);w.writerow(['pikoo','namespace','',''])
            for key,value in c.items():
                if key in ('ssid','password','endpoint','token'):w.writerow([key,'data','string',value])
        subprocess.run([sys.executable,str(generator),'generate',str(source),str(a.output.resolve()),'0x10000'],check=True,stdout=subprocess.DEVNULL)
    a.output.chmod(0o600)
    if a.port:subprocess.run([sys.executable,'-m','esptool','--chip','esp32s3','--port',a.port,'write_flash','0x9000',str(a.output.resolve())],check=True)
    print('Private NVS image created. Keep it out of GitHub; it contains Wi-Fi and device credentials.')
if __name__=='__main__':main()
