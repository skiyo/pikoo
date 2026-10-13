#!/usr/bin/env python3
"""Finite private training job: import -> train -> Micro runtime -> blind evaluation.
Download archives first. This script never publishes or replaces the public model.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--archives',type=Path,required=True)
    p.add_argument('--permission-record',type=Path,required=True)
    p.add_argument('--upstream',type=Path,required=True)
    p.add_argument('--micro-check',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--epochs',type=int,default=18)
    p.add_argument('--idf-path',type=Path)
    p.add_argument('--idf-tools',type=Path)
    a=p.parse_args();os.umask(0o077)
    scripts=Path(__file__).resolve().parent; output=a.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    status=output/'job-status.json'
    def record(stage, state='running'):
        status.write_text(json.dumps(dict(stage=stage,state=state,updated_at=datetime.now(timezone.utc).isoformat(),
            restricted=True,hardware_validated=False),indent=2)+'\n')
        print(stage,state,flush=True)
    def run(stage,argv,stdout=None,env=None):
        record(stage)
        with (output/(stage+'.log')).open('w') as log:
            if stdout:
                with stdout.open('w') as out:
                    subprocess.run(argv,check=True,stdout=out,stderr=log,env=env)
            else:
                subprocess.run(argv,check=True,stdout=log,stderr=subprocess.STDOUT,env=env)
    def python(name,*args):return [sys.executable,str(scripts/name),*map(str,args)]
    try:
        if bool(a.idf_path)!=bool(a.idf_tools):
            raise ValueError('Provide both --idf-path and --idf-tools for private firmware verification')
        # Expected exact archive sizes from pinned revision metadata, not partial downloads.
        for filename,size in [('train.tar',3875289600),('dev.tar',441251840),('test.tar',475832832)]:
            if (a.archives/filename).stat().st_size!=size:
                raise ValueError('Incomplete pinned archive: '+filename)
        children=output/'children'; combined=output/'manifest.json'; model=output/'model'
        run('import',python('import_childmandarin.py','--archives',a.archives,'--output',children,
            '--permission-record',a.permission_record))
        run('merge',python('merge_manifests.py',scripts/'data/synthetic/manifest.json',
            children/'manifest.json','--output',combined))
        run('train',python('train.py','--upstream',a.upstream,'--manifest',combined,
            '--output',model,'--epochs',a.epochs))
        run('micro-runtime',[str(a.micro_check.resolve()),str(model/'nihao_pikoo.tflite')],
            stdout=model/'micro-check.json')
        for name,path in [('baseline',scripts/'models/nihao_pikoo.tflite'),('candidate',model/'nihao_pikoo.tflite')]:
            run('evaluate-'+name,python('evaluate.py','--model',path,'--manifest',combined,
                '--output',output/(name+'-streaming.json')))
        baseline=json.loads((output/'baseline-streaming.json').read_text())
        candidate=json.loads((output/'candidate-streaming.json').read_text())
        comparison={'status':'experimental-private-candidate','child_wake_recall':None,
            'limitation':'Child corpus contains negatives only. No real-child wake-phrase recall or hardware claims.',
            'threshold':.9,'splits':{}}
        for split in ['validation','test']:
            comparison['splits'][split]={}
            for name,report in [('baseline',baseline),('candidate',candidate)]:
                s=report['splits'][split]
                comparison['splits'][split][name]={k:v for k,v in s.items() if k not in ('details','groups')}
                comparison['splits'][split][name]['groups']={k:v for k,v in s['groups'].items()
                    if k.startswith(('source:','age:'))}
        (output/'comparison.json').write_text(json.dumps(comparison,ensure_ascii=False,indent=2)+'\n')
        if a.idf_path:
            env=os.environ.copy();env['IDF_TOOLS_PATH']=str(a.idf_tools.resolve())
            env['PATH']=str(a.idf_tools.resolve()/'python_env/idf5.5_py3.11_env/bin')+os.pathsep+env['PATH']
            command='set -e; source "$1/export.sh"; exec idf.py -C "$2" -B "$3" "-DPIKOO_WAKE_MODEL=$4" build'
            run('firmware-build',['bash','-c',command,'pikoo-private-build',str(a.idf_path.resolve()),
                str(scripts.parent/'firmware'),str(output/'firmware-build'),str(model/'nihao_pikoo.tflite')],env=env)
        record('offline-evaluation-complete','complete')
    except BaseException as error:
        # Exception text may contain paths; complete diagnostic stays in this private run.
        record('failed','failed')
        (output/'failure.txt').write_text(str(error)+'\n')
        raise


if __name__=='__main__':main()
