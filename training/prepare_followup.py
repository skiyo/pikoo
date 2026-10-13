#!/usr/bin/env python3
"""Retire v4 test and freeze a fresh waveform challenge for causal v5 training."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import numpy as np
from prepare_iteration import read,trim,write,TARGETS,NEGATIVES,TEST
from self_test import NEGATIVES as PREVIOUS_NEGATIVES
import subprocess,tempfile


def main():
    p=argparse.ArgumentParser();p.add_argument('--previous',type=Path,required=True)
    p.add_argument('--challenge',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();os.umask(0o077);a.output.mkdir(parents=True,exist_ok=True)
    audio=a.output/'audio';raw=a.output/'raw';audio.mkdir(exist_ok=True);raw.mkdir(exist_ok=True)
    old=json.loads(a.previous.read_text());rows=[]
    for r in old:
        if r['split']=='test' and not r.get('real_child'):continue
        rows.append({**r,'path':os.path.relpath((a.previous.parent/r['path']).resolve(),a.output.resolve())})
    # Old Sandy challenge is now explicitly development validation, not blind data.
    for r in json.loads(a.challenge.read_text()):
        if r['voice']!='Sandy (中文（中国大陆）)' or r['kind']=='homophone':continue
        rows.append(dict(path=os.path.relpath((a.challenge.parent/r['path']).resolve(),a.output.resolve()),
            label=int(r['kind']=='positive'),split='validation',speaker=r['voice'],group=r['voice'],
            voice=r['voice'],text=r['text'],source='known-self-test-v1-validation',real_child=False))
    negatives=list(dict.fromkeys(NEGATIVES+PREVIOUS_NEGATIVES+['今天的天气有点凉','我想喝一杯水',
        '我们刚才在公园玩','请打开右边的灯','你好，小机器人','你的皮球在哪儿']))
    jobs=[]
    for voice in TEST:
        jobs += [(voice,t,r) for t in TARGETS for r in [105,167,249]]
        jobs += [(voice,t,r) for t in negatives for r in [149,239]]
        jobs += [(voice,'嘿',175),(voice,'你现在在听吗',175)]
    def synth(job):
        voice,text,rate=job;key=hashlib.sha256(f'v5:{voice}:{text}:{rate}'.encode()).hexdigest()[:24]
        path=raw/(key+'.wav')
        if not path.exists():
            with tempfile.TemporaryDirectory() as tmp:
                src=Path(tmp)/'speech.aiff'
                subprocess.run(['say','-v',voice,'-r',str(rate),'-o',str(src),text],check=True,capture_output=True,timeout=90)
                subprocess.run(['afconvert','-f','WAVE','-d','LEI16@16000','-c','1',str(src),str(path)],check=True,capture_output=True,timeout=30)
        return job,trim(read(path))
    clips={}
    with ThreadPoolExecutor(max_workers=3) as pool:
        for n,(key,pcm) in enumerate(pool.map(synth,jobs)):
            clips[key]=pcm
            if n%25==0:print('New blind synthesis',n+1,'/',len(jobs),flush=True)
    new=[]
    for voice in TEST:
        for text in TARGETS:
            for rate in [105,167,249]:
                target=clips[(voice,text,rate)]
                for context in ['isolated','prefix','suffix']:
                    before=clips[(voice,'嘿',175)] if context=='prefix' else np.empty(0,np.int16)
                    after=clips[(voice,'你现在在听吗',175)] if context=='suffix' else np.empty(0,np.int16)
                    if len(before):before=np.concatenate([before,np.zeros(1600,np.int16)])
                    pcm=np.concatenate([before,target,np.zeros(1600,np.int16),after]);key=hashlib.sha256(pcm.tobytes()).hexdigest()
                    path=audio/(key+'.wav');write(path,pcm)
                    new.append(dict(path=str(path.relative_to(a.output)),label=1,split='test',
                        speaker=voice,group=voice,voice=voice,text=text,context=context,rate=rate,
                        source='macOS-frozen-v5-test',real_child=False))
        for text in negatives:
            for rate in [149,239]:
                pcm=clips[(voice,text,rate)];key=hashlib.sha256(pcm.tobytes()).hexdigest();path=audio/(key+'.wav');write(path,pcm)
                new.append(dict(path=str(path.relative_to(a.output)),label=0,split='test',speaker=voice,group=voice,
                    voice=voice,text=text,rate=rate,source='macOS-frozen-v5-test',real_child=False))
    seen={hashlib.sha256((a.previous.parent/r['path']).read_bytes()).hexdigest() for r in old}
    excluded=0
    for r in new:
        digest=hashlib.sha256((a.output/r['path']).read_bytes()).hexdigest()
        if digest in seen:excluded+=1;continue
        seen.add(digest);rows.append(r)
    group_split={};hash_split={}
    for r in rows:
        group=r.get('speaker',r.get('voice',r['group']));digest=hashlib.sha256((a.output/r['path']).read_bytes()).hexdigest()
        if group in group_split and group_split[group]!=r['split']:raise ValueError('Speaker leakage')
        if digest in hash_split and hash_split[digest]!=r['split']:raise ValueError('Waveform leakage')
        group_split[group]=r['split'];hash_split[digest]=r['split']
    (a.output/'manifest.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    report={'test_version':'v5-frozen-before-training','excluded_previous_waveforms':excluded,
        'retired_test':'v4 test is regression only after results were seen',
        'splits':{s:{'positive':sum(r['split']==s and r['label']==1 for r in rows),
                    'negative':sum(r['split']==s and r['label']==0 for r in rows)} for s in ['train','validation','test']}}
    (a.output/'preparation-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
