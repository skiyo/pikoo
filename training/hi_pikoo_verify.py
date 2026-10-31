#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Verify trained candidates on TRAIN fixtures with native Micro kernels.

Freezes a candidate only after full DEV and backend checks, never accesses
sealed TEST or household recordings and never flashes a device.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import numpy as np


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--comparison', type=Path, required=True)
    p.add_argument('--micro-check', type=Path, required=True)
    p.add_argument('--freeze-output', type=Path, required=True)
    a = p.parse_args()
    from streaming_runtime import interpreter, quantize
    reports = json.loads((a.comparison/'comparison.json').read_text())
    if len(reports) != 4 or {(r['context_steps'], r['seed']) for r in reports} != {
            (20, 42), (20, 43), (72, 42), (72, 43)}:
        raise ValueError('All four predeclared comparisons must finish before selection')
    from hi_pikoo_contract import validate_contract
    contract = validate_contract(json.loads((a.comparison/'target-contract.json').read_text()))
    data = np.load(a.comparison/'features.npz')
    x, y, weights = data['train_x'], data['train_y'], data['train_w']
    labels = y.max(axis=1) > 0
    chosen = []
    for label in (False, True):
        indexes = np.flatnonzero(labels == label)
        if len(indexes) < 4:
            raise ValueError('Balanced TRAIN parity fixtures required')
        chosen.extend(indexes[np.linspace(0, len(indexes)-1, 4).astype(int)])
    eligible = []
    for report in reports:
        folder = a.comparison/f'context-{report["context_steps"]}-seed-{report["seed"]}'
        model = folder/'hi_pikoo.tflite'
        if sha(model) != report['static']['sha256']:
            raise ValueError('Candidate changed since complete DEV evaluation')
        cases = []
        for index in chosen:
            run = interpreter(model)
            run.allocate_tensors()
            inp, out = run.get_input_details()[0], run.get_output_details()[0]
            scale, zero = inp['quantization']
            steps = int(np.flatnonzero(weights[index] > 0)[-1])+1
            features = quantize(x[index, :steps*3], scale, zero)
            expected = []
            for start in range(0, len(features), 3):
                run.set_tensor(inp['index'], features[None, start:start+3])
                run.invoke()
                expected.append(int(run.get_tensor(out['index']).flat[0]))
            fixture = folder/f'train-{index}.int8'
            trace = fixture.with_suffix('.trace')
            fixture.write_bytes(features.tobytes())
            result = subprocess.run([str(a.micro_check.resolve()), str(model.resolve()),
                str(fixture.resolve()), '--trace-output', str(trace.resolve())],
                check=True, capture_output=True, text=True)
            native = json.loads(result.stdout.strip().splitlines()[-1])
            actual = np.frombuffer(trace.read_bytes(), np.uint8)
            wanted = np.tile(np.asarray(expected, np.uint8), 3)
            passed = actual.shape == wanted.shape and np.array_equal(actual, wanted)
            cases.append({'train_feature_index': int(index), 'label': bool(labels[index]),
                'steps': steps, 'reset_rounds': 3, 'byte_exact': bool(passed),
                'host_arena_bytes': native['host_arena_used_bytes']})
        proof = {'model_sha256': sha(model), 'cases': cases,
            'micro_executable_sha256': sha(a.micro_check),
            'passed': all(c['byte_exact'] and c['host_arena_bytes'] <= 262144 for c in cases),
            'scope': 'TRAIN-only builtin reference vs pinned native Micro; HOST allocation',
            'esp32_verified': False, 'household_or_test_used': False}
        (folder/'micro-parity.json').write_text(json.dumps(proof, indent=2)+'\n')
        selected = report['development']['selected']
        if proof['passed'] and selected is not None:
            # A qualifying model gets complete DEV replay on native Micro,
            # beyond the balanced TRAIN-only backend fixtures above.
            from hi_pikoo_model import select_policy
            dev_cases = json.loads((folder/'dev-cases.json').read_text())
            if len(dev_cases) != len(data['dev_x']):
                raise ValueError('Incomplete DEV provenance')
            native_cases = []
            for index, (features, case) in enumerate(zip(data['dev_x'], dev_cases)):
                run = interpreter(model)
                run.allocate_tensors()
                inp, out = run.get_input_details()[0], run.get_output_details()[0]
                scale, zero = inp['quantization']
                oscale, ozero = out['quantization']
                n = case['valid_steps']
                fixture = folder/'dev-replay.int8'
                trace = folder/'dev-replay.trace'
                fixture.write_bytes(quantize(features[:n*3], scale, zero).tobytes())
                subprocess.run([str(a.micro_check.resolve()), str(model.resolve()),
                    str(fixture.resolve()), '--trace-output', str(trace.resolve())],
                    check=True, capture_output=True, text=True)
                raw = np.frombuffer(trace.read_bytes(), np.uint8).reshape(3, n)
                wanted = np.rint(np.asarray(case['probabilities'])/oscale+ozero).astype(np.uint8)
                if not np.array_equal(raw, np.tile(wanted, (3, 1))):
                    raise ValueError('Native complete DEV differs from reference: '+str(index))
                native_cases.append({**case, 'probabilities': ((raw[0].astype(float)-ozero)*oscale).tolist()})
            native_policy = select_policy(native_cases)
            if native_policy['selected'] != selected:
                raise ValueError('Native complete DEV changes the selected policy')
            (folder/'micro-dev.json').write_text(json.dumps({'cases': len(native_cases),
                'reset_rounds': 3, 'byte_exact': True, 'development': native_policy,
                'real_child_or_device_acceptance': False}, indent=2)+'\n')
            eligible.append((report, folder, selected))
    eligible.sort(key=lambda item: (-item[2]['worst_recall'], item[2]['latency_p95_ms'],
                                   item[0]['static']['bytes'], item[0]['seed']))
    decision = {'eligible_candidates': len(eligible), 'test_opened': False,
        'hardware_accepted': False, 'status': 'rejected-no-qualified-candidate'}
    if eligible:
        report, folder, policy = eligible[0]
        sys.path.insert(0, str(Path(__file__).parents[1]/'tools'))
        from check_wake_policy import frontend_fingerprint, validate
        a.freeze_output.mkdir(parents=True, exist_ok=False)
        target = a.freeze_output/'hi_pikoo.tflite'
        shutil.copyfile(folder/'hi_pikoo.tflite', target)
        bundle = {'schema_version': 1, 'target': contract['target'], 'accepted_names': contract['accepted_names'],
            'model_sha256': sha(target), 'rolling': policy['rolling'],
            'threshold': policy['threshold'],
            'candidate_frozen_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'development_passed': True, 'frontend_fingerprint': frontend_fingerprint(),
            'frontend': {'sample_rate': 16000, 'feature_bins': 40,
                'window_ms': 30, 'feature_step_ms': 10, 'inference_step_ms': 30},
            'source_report_sha256': sha(folder/'report.json'),
            'micro_proof_sha256': sha(folder/'micro-parity.json'),
            'source': folder.name, 'real_child_accepted': False,
            'sealed_test_passed': False, 'esp32_resource_accepted': False,
            'release_eligible': False}
        validate(target, bundle)
        (a.freeze_output/'wake-policy.json').write_text(json.dumps(bundle, indent=2)+'\n')
        decision.update(status='candidate-frozen-awaiting-fresh-test-and-device', source=folder.name)
    (a.comparison/'candidate-decision.json').write_text(json.dumps(decision, indent=2)+'\n')
    print(json.dumps(decision))


if __name__ == '__main__':
    main()
