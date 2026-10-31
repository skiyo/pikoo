#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Blind quality screen of a NEW sealed synthetic test, bound to one candidate.

No model selection or household audio. No test replacement/regeneration. The
local ASR is content evidence only; vowel groups and ages are not gold labels.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_test(row, root, protected, policy):
    if (row.get('split') != 'test' or row.get('evaluation_only') is not True or
        row.get('frozen_holdout') is not True or not row.get('synthetic') or
        row.get('source') != 'OpenAI-Realtime-synthetic' or row.get('real_child') or
        row.get('family_inputs_used') or row.get('reference_audio_used') or
        row.get('sha256') in protected or row.get('parent_sha256') or
        row.get('frozen_candidate_sha256') != policy['model_sha256']):
        raise ValueError('Only the new sealed fictional test for this frozen candidate is allowed')
    path = (root/row['path']).resolve()
    if not path.is_relative_to(root.resolve()) or sha(path) != row['sha256']:
        raise ValueError('Sealed original path/hash mismatch')
    return path


def frozen(model, policy_path, allow_trial=False):
    import sys
    sys.path.insert(0, str(Path(__file__).parents[1]/'tools'))
    from check_wake_policy import validate
    policy = json.loads(policy_path.read_text())
    validate(model, policy, allow_trial)
    return policy


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','model','policy','protected-hashes','admitted-manifest','asr-model','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--allow-trial',action='store_true')
    a=p.parse_args();os.umask(0o077)
    policy=frozen(a.model,a.policy,a.allow_trial)
    rows=json.loads(a.manifest.read_text())
    protected=set(json.loads(a.protected_hashes.read_text())['audio_sha256'].values())
    admitted=json.loads(a.admitted_manifest.read_text())
    seen_sha={r['sha256'] for r in admitted}
    seen_speakers={r['speaker'] for r in admitted}
    if len({r['sha256'] for r in rows}) != len(rows):
        raise ValueError('Duplicate test recordings')
    paths=[]
    for row in rows:
        if row['speaker'] in seen_speakers or row['sha256'] in seen_sha:
            raise ValueError('Test speaker or waveform crosses TRAIN/DEV')
        paths.append(validate_test(row,a.manifest.parent,protected,policy))
    if a.output.exists():
        old=json.loads(a.output.read_text())
        if old['manifest_sha256'] != sha(a.manifest) or old['policy_sha256'] != sha(a.policy):
            raise ValueError('Sealed review is bound to another manifest/policy')
        if old.get('complete'):return
        cached={r['sha256']:r for r in old['records']}
    else:cached={}
    if not a.asr_model.is_dir():raise ValueError('Existing local ASR model required')
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    from mlx_audio.stt.utils import load_model
    import mlx.core as mx
    mx.set_cache_limit(128*1024*1024)
    model=load_model(str(a.asr_model.resolve()))
    from hi_pikoo_review import content_match
    from hi_pikoo_train import read_audio
    from hi_pikoo_timing import timing
    result=[]
    for row,path in zip(rows,paths):
        if row['sha256'] in cached:item=cached[row['sha256']]
        else:
            text=model.generate(str(path),max_tokens=96,temperature=0,verbose=False).text.strip()
            details=timing(read_audio(path))
            ok=(content_match(row,text) and content_match(row,row.get('transcript',''))
                and (not row['label'] or .3 <= details['view_ms']/1000 <= 3.5))
            item={'sha256':row['sha256'],'transcript':text,'quality_valid':bool(ok),
                  'timing':details,'quality_is_not_phoneme_or_age_gold':True}
        result.append(item)
        report={'manifest_sha256':sha(a.manifest),'model_sha256':sha(a.model),
            'policy_sha256':sha(a.policy),'complete':len(result)==len(rows),
            'records':result,'household_used':False,'model_scored':False}
        a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'reviewed':len(result),'total':len(rows),'quality_valid':sum(r['quality_valid'] for r in result)}),flush=True)


if __name__=='__main__':main()
