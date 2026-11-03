#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""One-shot full mixed-source TEST of an immutable native candidate/policy.

No provider calls, recordings, threshold search, augmentation or device access.
The entire untrimmed waveform is scored. Consumption is sealed before inference.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess

from wake_mixed_test import ROOT, sha, validate_bundle


def preflight(args):
    from hi_pikoo_sealed_review import frozen
    policy = frozen(args.model, args.policy)
    proof = json.loads(args.native_proof.read_text())
    if (sha(args.native_proof) != policy.get('micro_proof_sha256') or
            proof.get('model_sha256') != sha(args.model) or proof.get('passed') is not True or
            sha(args.micro_check) != proof.get('micro_sha256')):
        raise ValueError('Exact pinned native backend and pre-TEST parity proof required')
    protection = json.loads(args.protected_hashes.read_text())
    for name, digest in protection['source_metadata_sha256'].items():
        if sha(Path(name)) != digest:
            raise ValueError('Prior-source protection metadata changed after protocol declaration')
    plan = json.loads(args.protocol.read_text())
    rows = json.loads(args.manifest.read_text())
    review = json.loads(args.review.read_text())
    cases = validate_bundle(plan, rows, review, args.manifest.parent, policy, sha(args.policy),
        set(protection['audio_sha256'].values()), sha(args.protected_hashes),
        sha(args.manifest), sha(args.protocol), getattr(args, 'source_repair', None), args.policy)
    return policy, protection, cases


def checked_trace(data, steps):
    if type(steps) is not int or steps <= 0 or len(data) != steps * 3:
        raise ValueError('Truncated native probability trace')
    first = data[:steps]
    if data != first * 3:
        raise ValueError('Native state reset replay differs')
    return first


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('protocol', 'manifest', 'review', 'model', 'policy', 'protected-hashes',
                 'native-proof', 'micro-check', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--source-repair', type=Path)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(ROOT) or args.output.exists():
        parser.error('Choose a new private output directory outside the source repository')
    os.umask(0o077)
    policy, protection, cases = preflight(args)
    if (args.policy.parent / 'sealed-test-consumption.json').exists():
        raise ValueError('Candidate already has a consumed sealed TEST; do not call it new')
    marker = args.policy.parent / 'independent-TEST-consumption.json'
    consumption = {'started_at': datetime.now(timezone.utc).isoformat(),
        'status': 'started-consumed-not-fresh-on-retry', 'model_sha256': sha(args.model),
        'policy_sha256': sha(args.policy), 'protocol_sha256': sha(args.protocol),
        'manifest_sha256': sha(args.manifest), 'review_sha256': sha(args.review),
        'recording_sha256': {c['id']: c['sha256'] for c in cases}}
    if args.source_repair:
        consumption['source_repair_plan_sha256'] = sha(args.source_repair)
    # Exclusive marker comes first: an inference/import failure still consumes it.
    with marker.open('x') as file:
        json.dump(consumption, file, indent=2)
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    from streaming_runtime import interpreter, quantize
    from hi_pikoo_train import read_audio, features_and_times
    from hi_pikoo_model import policy_metrics
    import numpy as np
    run = interpreter(args.model); run.allocate_tensors()
    inp, out = run.get_input_details()[0], run.get_output_details()[0]
    if (list(inp['shape']) != [1, 3, 40] or inp['dtype'] != np.int8 or
            int(np.prod(out['shape'])) != 1 or out['dtype'] != np.uint8):
        raise ValueError('Frozen streaming ABI changed')
    scale, zero = out['quantization']
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError('Invalid output quantization')
    results = []
    for case in cases:
        # No training example() call: it crops long negatives and adds random
        # leading/trailing silence, neither of which is a raw family TEST.
        spec, times = features_and_times(read_audio(case['path']))
        steps = len(spec) // 3
        if steps < policy['rolling']:
            raise ValueError('TEST recording has insufficient streaming features')
        fixture = args.output / (case['id'] + '.int8')
        trace = fixture.with_suffix('.trace')
        fixture.write_bytes(quantize(spec[:steps*3], *inp['quantization']).tobytes())
        response = subprocess.run([str(args.micro_check.resolve()), str(args.model.resolve()),
            str(fixture.resolve()), '--trace-output', str(trace.resolve())],
            capture_output=True, text=True, check=True, timeout=60)
        actual = np.frombuffer(checked_trace(trace.read_bytes(), steps), np.uint8)
        native = json.loads(response.stdout.strip().splitlines()[-1])
        if native['host_arena_used_bytes'] > 262144:
            raise ValueError('Native host arena exceeds candidate resource gate')
        results.append({k: v for k, v in case.items() if k != 'path'} | {
            'times_ms': times[2:steps*3:3].tolist(),
            'probabilities': ((actual.astype(float)-zero)*scale).tolist(),
            'native_reset_rounds': 3, 'whole_waveform_used': True,
            'host_arena_bytes': native['host_arena_used_bytes']})
        (args.output / 'cases.partial.json').write_text(json.dumps(results) + '\n')
    metrics = policy_metrics(results, policy['rolling'], policy['threshold'])
    report = {'status': 'mixed-independent-TEST-completed',
        **{k: consumption[k] for k in ('model_sha256', 'policy_sha256', 'protocol_sha256', 'manifest_sha256')},
        'fixed_policy': {k: policy[k] for k in ('rolling', 'threshold')},
        'metrics': metrics, 'cases': len(results),
        'real_child_TEST_cases': sum(c['role']=='child' for c in results),
        'family_TEST_only': True, 'model_or_policy_selected_using_TEST': False,
        'hardware_resource_or_concurrency_passed': False, 'family_two_sessions_passed': False,
        'eight_hour_background_passed': False, 'formal_goal_completed': False}
    if args.source_repair:
        report['source_repair_plan_sha256'] = consumption['source_repair_plan_sha256']
        report['source_quality_repair'] = {
            'original_rejected_source_attempts_retained': 4,
            'additional_predeclared_benchmark_attempts': 4,
            'scored_slots_unchanged': 150,
            'recipe_auditions_scored': False,
            'not_a_retry_after_KWS_scores': True}
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    protection['audio_sha256'].update({'consumed-mixed-TEST/' + c['id']: c['sha256'] for c in cases})
    (args.output / 'protected-including-consumed-TEST.json').write_text(json.dumps(protection, indent=2) + '\n')
    consumption.update(status='completed-consumed', report_sha256=sha(args.output / 'report.json'))
    marker.write_text(json.dumps(consumption, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'TEST_passed': metrics['passed'],
                      'formal_goal_completed': False}))


if __name__ == '__main__': main()
