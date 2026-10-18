#!/usr/bin/env python3
"""Score validation or a frozen test set separately, with fixed threshold.
Real child recordings are negative-only; this never claims child wake recall.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import numpy as np
from evaluate import predict
from self_test import load, modify, CONDITIONS


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--model',type=Path,required=True);p.add_argument('--previous',type=Path,required=True)
    p.add_argument('--split',choices=['validation','test'],required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--clean-only',action='store_true')
    p.add_argument('--lead-seconds',type=float,default=1.,help='Explicit diagnostic startup context; default preserves historical 1s silence')
    p.add_argument('--background-rms',type=float,default=0.,help='Deterministic simulated PCM background; changes the evaluation convention, not labels')
    p.add_argument('--warmup-frames',type=int,default=0,help='Explicit model startup contract; masks only incomplete recurrent state, preserves default cold evaluation')
    a=p.parse_args();os.umask(0o077)
    if not math.isfinite(a.lead_seconds) or not 1<=a.lead_seconds<=10 or not math.isfinite(a.background_rms) or not 0<=a.background_rms<=200:raise ValueError('Invalid diagnostic input context')
    if not 0<=a.warmup_frames<=900 or a.warmup_frames%3 or (a.warmup_frames and a.lead_seconds*100<a.warmup_frames+14):raise ValueError('Warmup requires a full horizon and five valid outputs before the utterance')
    manifest=json.loads(a.manifest.read_text());rows=[r for r in manifest if r['split']==a.split]
    models={'previous':a.previous,'candidate':a.model}
    hashes={k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in models.items()}
    conditions=['clean'] if a.clean_only else CONDITIONS
    rng=np.random.default_rng(20261014);details=[]
    background_rng=np.random.default_rng(20261018)
    for n,row in enumerate(rows):
        pcm=load(a.manifest.parent/row['path'])
        for condition in conditions:
            x=modify(pcm,condition,rng)
            samples=np.pad(x,(round(a.lead_seconds*16000),16000))
            if a.background_rms:
                samples=np.clip(samples+background_rng.normal(0,a.background_rms,len(samples)),-32768,32767).astype('<i2')
            scores={k:predict(path,samples,a.warmup_frames) for k,path in models.items()}
            details.append({'label':row['label'],'source':row.get('source'),'sha256':row.get('sha256') or hashlib.sha256((a.manifest.parent/row['path']).read_bytes()).hexdigest(),
                'speaker':row.get('speaker',row.get('voice')),'real_child':row.get('real_child',False),
                'age':row.get('age'),'text':None if row.get('real_child') else row.get('text'),
                'evaluation_only':row.get('evaluation_only',False),'frozen_holdout':row.get('frozen_holdout',False),
                'pronunciation':row.get('pronunciation'),'synthetic_style':row.get('synthetic_style'),
                'condition':condition,'context':row.get('context'),
                'seconds':len(x)/16000,'scores':scores,'detected':{k:v>=.9 for k,v in scores.items()}})
        if n%50==0:print('Scored',n+1,'/',len(rows),flush=True)
    summaries={}
    for condition in conditions:
        summaries[condition]={}
        for model in models:
            group=[r for r in details if r['condition']==condition]
            report={}
            groups={'all':group,'synthetic':[r for r in group if not r['real_child']],
                    'real_child':[r for r in group if r['real_child']]}
            for voice in {r['speaker'] for r in group if not r['real_child']}:
                groups['voice:'+voice]=[r for r in group if r['speaker']==voice]
            for context in {r['context'] for r in group if r['label']}:
                groups['context:'+str(context)]=[r for r in group if r['label'] and r['context']==context]
            for field in ('source','pronunciation','synthetic_style'):
                for value in {r.get(field) for r in group if r.get(field) is not None}:
                    groups[field+':'+str(value)]=[r for r in group if r.get(field)==value]
            for name,sub in groups.items():
                pos=[r for r in sub if r['label']];neg=[r for r in sub if not r['label']]
                report[name]={'positive_clips':len(pos),'wake_detected':sum(r['detected'][model] for r in pos),
                    'negative_clips':len(neg),'false_positive_clips':sum(r['detected'][model] for r in neg),
                    'negative_seconds':sum(r['seconds'] for r in neg)}
            summaries[condition][model]=report
    report={'status':'offline-only-not-human-or-hardware-validation','split':a.split,
        'runtime':'TFLite reference kernels; firmware float32 half-away input quantization',
        'threshold':.9,'models':hashes,'conditions':summaries,'details':details}
    report['input_context']={'lead_seconds':a.lead_seconds,'background_rms':a.background_rms}
    if a.warmup_frames:report['input_context']['warmup_feature_frames']=a.warmup_frames
    report['background_seed']=20261018
    for model,path in models.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest()==hashes[model],'Model changed during evaluation'
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='details'},ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
