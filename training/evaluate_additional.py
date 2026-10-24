#!/usr/bin/env python3
"""Score the entire disclosed supplemental development manifest, never TRAIN."""
import argparse
import hashlib
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('model', 'manifest', 'protected-hashes', 'base-gate', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
    os.environ.setdefault('TF_NUM_INTRAOP_THREADS', '1')
    os.environ.setdefault('TF_NUM_INTEROP_THREADS', '1')
    from generalization_gate import assess
    from evaluate import predict
    from self_test import load
    import numpy as np
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    model_sha = digest(args.model)
    rows = json.loads(args.manifest.read_text())
    protected = set(json.loads(args.protected_hashes.read_text())['audio_sha256'].values())
    base = json.loads(args.base_gate.read_text())
    # Validate full identities, split and protection policy before decoding.
    assess({'threshold': .9, 'rolling_inferences': 5,
            'input_context': {'lead_seconds': 1., 'background_rms': 0.},
            'details': [{**row, 'detected': {'candidate': False}} for row in rows]},
           rows, base, protected)
    details = []
    for index, row in enumerate(rows):
        path = (args.manifest.parent / row['path']).resolve()
        if row['sha256'] in protected or digest(path) != row['sha256']:
            raise ValueError('Protected or changed supplemental recording')
        score = predict(args.model, np.pad(load(path), (16000, 16000)))
        details.append({**{key: value for key, value in row.items() if key != 'path'},
                        'scores': {'candidate': score}, 'detected': {'candidate': score >= .9}})
        if index % 20 == 0:
            print(json.dumps({'completed': index + 1, 'total': len(rows)}), flush=True)
    if digest(args.model) != model_sha:
        raise ValueError('Model changed during development evaluation')
    evaluation = {'threshold': .9, 'rolling_inferences': 5,
                  'input_context': {'lead_seconds': 1., 'background_rms': 0.},
                  'model_sha256': model_sha, 'details': details}
    gate = assess(evaluation, rows, base, protected)
    args.output.write_text(json.dumps(evaluation, ensure_ascii=False, indent=2) + '\n')
    args.output.with_suffix('.gate.json').write_text(json.dumps(gate, indent=2) + '\n')
    print(json.dumps(gate), flush=True)


if __name__ == '__main__':
    main()
