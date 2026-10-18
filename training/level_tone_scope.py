"""Explicit user-requested pī kū scope, preserving negatives and old reports.

Removed positive pronunciations are unspecified, never relabeled non-targets.
This is a new development contract, not a retroactive success on old tests.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
from streaming_gate import count

PRONUNCIATION='mixed-pi1-ku1'


def focused(rows,protected=()):
    protected=set(protected)
    for row in rows:
        if row.get('evaluation_only') or row.get('frozen_holdout') or str(row.get('source','')).startswith('private-') or row['sha256'] in protected:
            raise ValueError('Protected recordings cannot define or train this scope')
    return [dict(r) for r in rows if not r['label'] or r.get('pronunciation')==PRONUNCIATION]


def identity(rows):
    return Counter((r['sha256'],r['label'],r.get('pronunciation'),r.get('synthetic_style'),r['source']) for r in rows)


def assess(evaluation,policy,expected,model_bytes):
    rows=evaluation['details']
    if identity(rows)!=identity(expected):raise ValueError('Missing or changed development rows, including mandatory negatives')
    if focused(rows)!=rows:raise ValueError('Unexpected positive pronunciation')
    if evaluation['threshold']!=policy['threshold'] or policy['rolling_inferences']!=5:
        raise ValueError('Streaming cutoff/rolling contract differs')
    if evaluation.get('input_context')!=policy['input_context'] or any(r.get('condition')!='clean' for r in rows):
        raise ValueError('Development audio context differs')
    failures=[]
    def recall(group,name):
        values=count(group)
        if not values['targets'] or values['hits']/values['targets']<policy['min_recall']:failures.append(name)
        return values
    all_=recall(rows,'all-level-targets')
    if all_['false_wakes']>policy['max_false_wakes']:failures.append('false-wakes')
    if model_bytes>policy['firmware_max_bytes']:failures.append('model-size')
    raw=[r for r in rows if not r['source'].startswith('pitch-tempo-augmented-')]
    groups={style:recall([r for r in raw if r.get('synthetic_style')==style],style+'-raw-level-targets')
            for style in ['adult','childlike']}
    augmented=recall([r for r in rows if r['source'].startswith('pitch-tempo-augmented-')],'pitch-tempo-level-targets')
    return {'status':'passed-level-tone-development' if not failures else 'failed-level-tone-development',
            'passed':not failures,'contract':policy['contract'],'failures':failures,
            'streaming_development':all_,'raw_style_groups':groups,'pitch_tempo':augmented,
            'model_bytes':model_bytes,'old_mandarin_pronunciation':'unspecified, not a negative',
            'household_or_independent_test_used':False,'hardware_or_real_child_accepted':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','evaluate'])
    for name in ['manifest','protected-hashes','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--model',type=Path)
    p.add_argument('--policy',type=Path,default=Path(__file__).parent/'policies/dualeye-pikoo-level-v1.json')
    a=p.parse_args();os.umask(0o077)
    protected=json.loads(a.protected_hashes.read_text())['audio_sha256'].values()
    original=json.loads(a.manifest.read_text());rows=focused(original,protected)
    if a.action=='prepare':
        a.output.mkdir(parents=True,exist_ok=True)
        for row in rows:row['path']=os.path.relpath((a.manifest.parent/row['path']).resolve(),a.output.resolve())
        (a.output/'manifest.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
        report={'contract':json.loads(a.policy.read_text())['contract'],
                'parent_manifest_sha256':hashlib.sha256(a.manifest.read_bytes()).hexdigest(),
                'retained':{split:{'targets':sum(r['label']==1 for r in rows if r['split']==split),
                                   'non_targets':sum(r['label']==0 for r in rows if r['split']==split)}
                            for split in ['train','validation']},
                'removed_positives':len(original)-len(rows),'labels_changed':0,
                'negatives_preserved':identity([r for r in rows if not r['label']])==identity([r for r in original if not r['label']]),
                'household_or_independent_used':False}
        (a.output/'scope.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
        return
    if not a.model:p.error('evaluate requires --model')
    import numpy as np
    from evaluate import predict
    from self_test import load
    rows=[r for r in rows if r['split']=='validation'];details=[]
    digest=hashlib.sha256(a.model.read_bytes()).hexdigest()
    for i,row in enumerate(rows):
        path=a.manifest.parent/row['path']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('Changed waveform')
        score=predict(a.model,np.pad(load(path),(16000,16000)))
        details.append({**{k:v for k,v in row.items() if k!='path'},'condition':'clean',
                        'scores':{'candidate':score},'detected':{'candidate':score>=.9}})
        if i%100==0:print(i+1,len(rows),flush=True)
    evaluation={'threshold':.9,'input_context':{'lead_seconds':1.,'background_rms':0.},
                'models':{'candidate':digest},'details':details}
    if hashlib.sha256(a.model.read_bytes()).hexdigest()!=digest:raise ValueError('Model changed during scoring')
    gate=assess(evaluation,json.loads(a.policy.read_text()),rows,a.model.stat().st_size)
    a.output.write_text(json.dumps(evaluation,ensure_ascii=False,indent=2)+'\n')
    a.output.with_suffix('.gate.json').write_text(json.dumps(gate,indent=2)+'\n');print(json.dumps(gate),flush=True)


if __name__=='__main__':main()
