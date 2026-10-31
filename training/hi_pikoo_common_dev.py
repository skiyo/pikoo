#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compare completed models on one existing DEV view, never sealed TEST.

Each experiment gets a separate four-model report compatible with native Micro
verification. Reusing DEV is explicitly model selection, not independent testing.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import numpy as np
from hi_pikoo_train import admit, replay
from hi_pikoo_model import select_policy
from hi_pikoo_contrast import family


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ('root', 'common-cache', 'manifest', 'protected-hashes', 'output'):
        p.add_argument('--'+flag, type=Path, required=True)
    p.add_argument('--experiment', action='append', required=True)
    a = p.parse_args()
    os.umask(0o077)
    protected = set(json.loads(a.protected_hashes.read_text())['audio_sha256'].values())
    rows = json.loads(a.manifest.read_text())
    validated = admit(rows, a.manifest.parent, protected)
    dev = {r['sha256']: r for r, _ in validated if r['split'] == 'validation'}
    info = json.loads((a.common_cache/'context-72-seed-42/dev-cases.json').read_text())
    if {m['sha256'] for m in info} != set(dev) or len(info) != len(dev):
        raise ValueError('The common cache is not the complete admitted DEV')
    for meta in info:
        meta.pop('probabilities', None)
        meta['contrast_class'] = family(dev[meta['sha256']])
    with np.load(a.common_cache/'features.npz') as data:
        vx = data['dev_x']
    if vx.shape != (len(info), 600, 40):
        raise ValueError('Common DEV feature dimensions differ')
    contract = (a.common_cache/'target-contract.json').read_bytes()
    from streaming_runtime import interpreter
    a.output.mkdir(parents=True, exist_ok=False)
    summary = []
    for experiment in a.experiment:
        source = (a.root/experiment).resolve()
        if not source.is_relative_to(a.root.resolve()):
            raise ValueError('Experiment escapes private run root')
        reports = json.loads((source/'comparison.json').read_text())
        if len(reports) != 4 or {(r['context_steps'], r['seed']) for r in reports} != {(20,42),(20,43),(72,42),(72,43)}:
            raise ValueError('Only complete predeclared comparisons are eligible')
        if (source/'target-contract.json').read_bytes() != contract:
            raise ValueError('Target revisions differ')
        target = a.output/experiment
        target.mkdir()
        os.link(a.common_cache/'features.npz', target/'features.npz')
        (target/'target-contract.json').write_bytes(contract)
        result = []
        for report in reports:
            name = f'context-{report["context_steps"]}-seed-{report["seed"]}'
            model = source/name/'hi_pikoo.tflite'
            if sha(model) != report['static']['sha256'] or report.get('sealed_test_scored'):
                raise ValueError('Changed model or invalid selection provenance')
            folder = target/name
            folder.mkdir()
            os.link(model, folder/'hi_pikoo.tflite')
            cases = [{**meta, 'probabilities': replay(interpreter(model), x)[:meta['valid_steps']]}
                     for x, meta in zip(vx, info)]
            policy = select_policy(cases)
            updated = {**report, 'development': policy,
                'source_report_sha256': sha(source/name/'report.json'),
                'selection_scope': 'same reused common DEV; not new TEST',
                'common_manifest_sha256': sha(a.manifest),
                'common_features_sha256': sha(a.common_cache/'features.npz')}
            (folder/'report.json').write_text(json.dumps(updated, indent=2)+'\n')
            (folder/'dev-cases.json').write_text(json.dumps(cases)+'\n')
            result.append(updated)
            print(json.dumps({'experiment': experiment, 'model': name,
                'status': policy['status'], 'best_worst_recall': max(q['worst_recall'] for q in policy['grid']),
                'min_false_wakes': min(q['false_wakes'] for q in policy['grid'])}), flush=True)
        (target/'comparison.json').write_text(json.dumps(result, indent=2)+'\n')
        summary.append({'experiment': experiment, 'models': len(result)})
    (a.output/'selection-provenance.json').write_text(json.dumps({
        'manifest_sha256': sha(a.manifest), 'protected_sha256': sha(a.protected_hashes),
        'common_dev_cases': len(info), 'experiments': summary,
        'household_used': False, 'new_test': False}, indent=2)+'\n')


if __name__ == '__main__':
    main()
