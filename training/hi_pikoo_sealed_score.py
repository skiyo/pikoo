#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""One frozen candidate/policy on a fresh sealed synthetic TEST, using Micro.

No threshold search, refit, family recording, provider call or device access.
Consumption is recorded before inference. A failed run is not a fresh test.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import numpy as np
from hi_pikoo_sealed_review import frozen,validate_test,sha
from hi_pikoo_model import policy_metrics
from hi_pikoo_train import read_audio,example


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','review','model','policy','protected-hashes','micro-check','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--allow-trial',action='store_true')
    a=p.parse_args();os.umask(0o077)
    policy=frozen(a.model,a.policy,a.allow_trial)
    review=json.loads(a.review.read_text())
    if (not review.get('complete') or review['manifest_sha256']!=sha(a.manifest)
            or review['model_sha256']!=sha(a.model) or review['policy_sha256']!=sha(a.policy)):
        raise ValueError('Complete candidate-bound blind quality review required')
    protected=set(json.loads(a.protected_hashes.read_text())['audio_sha256'].values())
    rows=json.loads(a.manifest.read_text())
    quality={r['sha256']:r for r in review['records']}
    paths=[validate_test(row,a.manifest.parent,protected,policy) for row in rows]
    # Do not rerun this consumed revision against a different model or policy.
    marker=a.policy.parent/'sealed-test-consumption.json'
    with marker.open('x') as file:
        json.dump({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'manifest_sha256':sha(a.manifest),'model_sha256':sha(a.model),
            'policy_sha256':sha(a.policy),'review_sha256':sha(a.review),
            'status':'started-consumed-not-a-new-test-on-retry'},file,indent=2)
    a.output.mkdir(parents=True,exist_ok=False)
    from streaming_runtime import interpreter,quantize
    run=interpreter(a.model);run.allocate_tensors()
    inp,out=run.get_input_details()[0],run.get_output_details()[0]
    scale,zero=inp['quantization'];oscale,ozero=out['quantization']
    from hi_pikoo_review import normalized
    cases=[]
    for index,(row,path) in enumerate(zip(rows,paths)):
        if not quality[row['sha256']]['quality_valid']:continue
        variant='piko' if normalized(quality[row['sha256']]['transcript'])=='hipiko' else 'piku'
        row={**row,'pronunciation_variant':variant if row['label'] else 'non-target'}
        seed=int.from_bytes(__import__('hashlib').sha256(('sealed-v1/'+row['sha256']).encode()).digest()[:8],'little')
        x,_,_,meta=example(read_audio(path),row,np.random.default_rng(seed))
        n=meta['valid_steps'];fixture=a.output/f'case-{index}.int8';trace=fixture.with_suffix('.trace')
        fixture.write_bytes(quantize(x[:n*3],scale,zero).tobytes())
        result=subprocess.run([str(a.micro_check.resolve()),str(a.model.resolve()),str(fixture.resolve()),
            '--trace-output',str(trace.resolve())],capture_output=True,text=True,check=True)
        raw=np.frombuffer(trace.read_bytes(),np.uint8).reshape(3,n)
        if not np.all(raw==raw[0]):raise ValueError('Native reset results differ')
        native=json.loads(result.stdout.strip().splitlines()[-1])
        cases.append({**meta,'probabilities':((raw[0].astype(float)-ozero)*oscale).tolist(),
                      'native_reset_rounds':3,'host_arena_bytes':native['host_arena_used_bytes']})
        (a.output/'cases.partial.json').write_text(json.dumps(cases)+'\n')
    if not cases or not any(c['label']==0 for c in cases) or not any(c['label']==1 for c in cases):
        raise ValueError('Fresh test has insufficient quality-valid classes')
    metrics=policy_metrics(cases,policy['rolling'],policy['threshold'])
    report={'status':'frozen-synthetic-adult-TEST-completed','model_sha256':sha(a.model),
        'policy_sha256':sha(a.policy),'manifest_sha256':sha(a.manifest),
        'fixed_policy':{'rolling':policy['rolling'],'threshold':policy['threshold']},
        'metrics':metrics,'generated':len(rows),'quality_valid':len(cases),
        'quality_invalid':len(rows)-len(cases),'real_child_tested':False,
        'household_used':False,'hardware_tested':False,'formal_goal_completed':False,
        'development_passed':policy['development_passed'],
        'trial_only':policy.get('trial_authorized',False),'model_or_policy_selected_using_test':False}
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    marker_data=json.loads(marker.read_text());marker_data['status']='completed-consumed';marker_data['report_sha256']=sha(a.output/'report.json')
    marker.write_text(json.dumps(marker_data,indent=2)+'\n')
    protection=json.loads(a.protected_hashes.read_text())
    protection['audio_sha256'].update({'sealed-test/'+r['id']:r['sha256'] for r in rows})
    (a.output/'protected-including-consumed-test.json').write_text(json.dumps(protection,indent=2)+'\n')
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
