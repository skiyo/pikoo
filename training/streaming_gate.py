#!/usr/bin/env python3
"""Fixed development gate for full streaming scores, never household selection.

The reused development split is not blind acceptance. A pass does not establish
ESP32 timing, background false-wake rate, or real child/adult performance.
"""
import argparse
import hashlib
import json
from pathlib import Path


def count(rows):
    positives=[r for r in rows if r['label']]
    negatives=[r for r in rows if not r['label']]
    return {'targets':len(positives),'hits':sum(r['detected']['candidate'] for r in positives),
            'non_targets':len(negatives),'false_wakes':sum(r['detected']['candidate'] for r in negatives)}


def assess(evaluation,policy,legacy_hashes,model_bytes):
    if evaluation['threshold']!=policy['threshold'] or policy['rolling_inferences']!=5:
        raise ValueError('Evaluation and fixed streaming gate disagree')
    rows=evaluation['details']
    if any(r.get('evaluation_only') or r.get('frozen_holdout') or str(r.get('source','')).startswith('private-') for r in rows):
        raise ValueError('Household/evaluation-only/frozen-holdout audio cannot select a candidate')
    if any(r.get('condition')!='clean' for r in rows):
        raise ValueError('Use the fixed clean streaming development corpus')
    original=[r for r in rows if r['sha256'] in legacy_hashes and r['label']]
    if len(legacy_hashes)!=policy['old_original_targets'] or len(original)!=len(legacy_hashes):
        raise ValueError('Legacy development targets are missing or duplicated')
    new=[r for r in rows if r['source']=='Qwen3-TTS-synthetic-local' and str(r.get('speaker','')).startswith('qwen-broad:')]
    failures=[]
    def recall(group,minimum,label):
        values=count(group)
        if not values['targets'] or values['hits']/values['targets']<minimum:failures.append(label)
    all_=count(rows)
    if model_bytes>policy['firmware_max_bytes']:failures.append('model-size')
    if all_['false_wakes']>policy['validation_non_target_false_wakes_max']:failures.append('false-wakes')
    if count(original)['hits']<policy['old_original_target_min_hits']:failures.append('legacy-original-recall')
    recall(new,policy['primary_new_targets_min_recall'],'new-primary-recall')
    groups={}
    for style in ['adult','childlike']:
        for pronunciation in ['mandarin-pi2-ku4','mixed-pi1-ku1']:
            key=style+':'+pronunciation
            group=[r for r in new if r.get('synthetic_style')==style and r.get('pronunciation')==pronunciation]
            groups[key]=count(group)
            recall(group,policy['each_new_pronunciation_and_style_min_recall'],key)
    augmented=[r for r in rows if str(r['source']).startswith('pitch-tempo-augmented-')]
    recall(augmented,policy['new_pitch_tempo_min_recall'],'pitch-tempo-recall')
    return {'status':'passed-development-gate' if not failures else 'failed-development-gate',
        'passed':not failures,'failures':failures,'model_bytes':model_bytes,
        'streaming_development':all_,'legacy_original':count(original),'new_primary':count(new),
        'new_style_pronunciation':groups,'pitch_tempo':count(augmented),
        'real_child_ordinary_speech':count([r for r in rows if r.get('real_child')]),
        'household_used_for_selection':False,'hardware_and_human_acceptance':'pending'}


def legacy_targets(manifest):
    return {r['sha256'] for r in manifest if r['split']=='validation' and r['label'] and r['source'] in
            {'macOS-aligned-v2','known-self-test-v1-validation','Google-Gemini-TTS-synthetic'}}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['evaluation','policy','legacy-manifest','model','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    evaluation=json.loads(a.evaluation.read_text());digest=hashlib.sha256(a.model.read_bytes()).hexdigest()
    if evaluation['models']['candidate']!=digest:raise ValueError('Evaluation/model hash mismatch')
    result=assess(evaluation,json.loads(a.policy.read_text()),legacy_targets(json.loads(a.legacy_manifest.read_text())),a.model.stat().st_size)
    result.update(model_sha256=digest,evaluation_sha256=hashlib.sha256(a.evaluation.read_bytes()).hexdigest())
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
