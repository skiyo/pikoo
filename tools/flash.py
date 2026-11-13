#!/usr/bin/env python3
"""Flash checked Pikoo build images, preserving all private partitions."""
import argparse
from pathlib import Path
from device import build_files,write

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',required=True);p.add_argument('--build',type=Path,default=Path(__file__).resolve().parents[1]/'firmware/build-dualeye');p.add_argument('--dry-run',action='store_true');a=p.parse_args()
    files,_=build_files(a.build)
    if a.dry_run:print('Build and private-partition preservation validated; no device accessed.')
    else:write(a.port,files)
if __name__=='__main__':main()
