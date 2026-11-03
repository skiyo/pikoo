#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Finalize a numerically frozen native candidate for fresh TEST tooling.

Requires complete synthetic DEV content review and eight TRAIN-only byte-exact
reference/Micro fixtures. Never opens TEST, household recordings or a device.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np
from hi_pikoo_model import GRID, policy_metrics


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_gate(frozen, review, original_manifest_sha256):
    result = frozen['evaluation']
    old = result['old_DEV']
    expected = {'adult:standard:piku': 28, 'adult:standard:piko': 3,
                'adult:Chinese-accent:piku': 27, 'adult:Chinese-accent:piko': 10,
                'childlike:Chinese-accent:piku': 11, 'childlike:Chinese-accent:piko': 13}
    required = {'adult:standard:piku': 26, 'adult:standard:piko': 3,
                'adult:Chinese-accent:piku': 26, 'adult:Chinese-accent:piko': 10,
                'childlike:Chinese-accent:piku': 11, 'childlike:Chinese-accent:piko': 12}
    policy = frozen.get('policy', {})
    if (set(policy) != {'rolling', 'threshold'} or
            (policy.get('rolling'), policy.get('threshold')) not in GRID or
            any(result.get(k) != v or old.get(k) != v for k, v in policy.items()) or
            result.get('qualified') is not True or old.get('passed') is not True or
            result.get('old_DEV_preserved') is not True or
            result.get('backend') != 'pinned native TFLite Micro' or
            result.get('household_used') is not False or result.get('TEST_opened') is not False or
            result.get('new_negative_DEV_cases') != 261 or
            result.get('new_negative_DEV_false_clips') != 0 or
            old.get('false_wakes') != 0 or old.get('early_wakes') != 0 or
            old.get('latency_p95_ms') is None or not np.isfinite(old['latency_p95_ms']) or
            not 0 <= old['latency_p95_ms'] <= 800 or
            set(result.get('required_group_hits', {})) != set(required) or
            any(not required[g] <= result['required_group_hits'][g] <= expected[g] for g in required) or
            {g: v['targets'] for g, v in old['groups'].items()} != expected or
            any(not 0 <= v['hits'] <= v['targets'] or v['hits']/v['targets'] < .9
                for v in old['groups'].values()) or
            any(old['groups'][g]['hits'] < n for g, n in result['required_group_hits'].items())):
        raise ValueError('Full unchanged native DEV gate is not proved')
    if (review.get('scope') != 'complete-original-synthetic-DEV-content-review' or
            review.get('original_manifest_sha256') != original_manifest_sha256 or
            review.get('all_pending_questions_resolved') is not True or
            review.get('labels_unchanged') is not True or
            review.get('household_used') is not False or
            set(review.get('reviewed_uncertainty_indices', [])) != {10, 21, 40, 57, 58, 60, 72} or
            review.get('review_clip_selection_used_wake_scores') is not False):
        raise ValueError('Resolve independent synthetic DEV content questions before TEST')
    return result


def verify_saved_dev(cases, negatives, result, policy, plan):
    """Never reuse another smoothing/threshold's negative peak summaries."""
    if any(plan.get(k) != v or result.get(k) != v for k, v in policy.items()):
        raise ValueError('Frozen policy differs from evaluated and declared policy')
    if (len(cases) != 144 or sum(not c['label'] for c in cases) != 52 or
            len(negatives) != 261):
        raise ValueError('Complete DEV trace evidence required')
    if policy_metrics(cases, **policy) != result['old_DEV']:
        raise ValueError('Frozen original DEV metrics do not match saved traces')
    false_clips = 0
    for case in negatives:
        peak = case.get('peak')
        if (not isinstance(peak, (int, float)) or isinstance(peak, bool) or
                not np.isfinite(peak) or not 0 <= peak <= 1):
            raise ValueError('Finite negative DEV peak evidence required')
        activated = bool(np.float32(peak) >= np.float32(policy['threshold']))
        if type(case.get('activated')) is not bool or case['activated'] != activated:
            raise ValueError('Negative DEV decisions disagree with selected policy')
        false_clips += activated
    if false_clips != result['new_negative_DEV_false_clips'] or false_clips:
        raise ValueError('Negative DEV gate differs from saved evidence')


def parity(model, micro, features, fixture):
    from streaming_runtime import interpreter, quantize
    run = interpreter(model)
    run.allocate_tensors()
    inp, out = run.get_input_details()[0], run.get_output_details()[0]
    if list(inp['shape']) != [1, 3, 40] or out['dtype'] != np.uint8:
        raise ValueError('Frozen candidate streaming ABI differs')
    data = quantize(features, *inp['quantization'])
    expected = []
    for start in range(0, len(data), 3):
        run.set_tensor(inp['index'], data[None, start:start+3])
        run.invoke()
        expected.append(int(run.get_tensor(out['index']).flat[0]))
    trace = fixture.with_suffix('.trace')
    fixture.write_bytes(data.tobytes())
    response = subprocess.run([str(micro.resolve()), str(model.resolve()), str(fixture.resolve()),
        '--trace-output', str(trace.resolve())], check=True, capture_output=True, text=True)
    proof = json.loads(response.stdout.strip().splitlines()[-1])
    actual = np.frombuffer(trace.read_bytes(), np.uint8)
    exact = actual.shape == (len(expected)*3,) and np.array_equal(actual, np.tile(expected, 3))
    return {'steps': len(expected), 'byte_exact': bool(exact), 'native_reset_rounds': 3,
            'host_arena_bytes': proof['host_arena_used_bytes']}


def base_representatives(plan, cached_count):
    retained = plan.get('retained_original_TRAIN_indices')
    retained = list(range(cached_count)) if retained is None else retained
    effective = plan.get('TRAIN_effective_examples', len(retained))
    selected = plan['representative_TRAIN_indices']
    if (any(not isinstance(i, int) or not 0 <= i < cached_count for i in retained) or
            any(not isinstance(i, int) or not 0 <= i < effective for i in selected)):
        raise ValueError('Malformed retained BASE or effective TRAIN fixture index')
    return [retained[i] for i in selected if i < len(retained)]


def verify_tempo(cases, metadata, result, review):
    """Recompute each new tempo gate from its complete saved native trace set."""
    from wake_dev_content_review import reviewed_cohorts
    keys = ('sha256', 'label', 'cohort', 'valid_steps', 'completion_ms', 'times_ms', 'tempo_factor')
    if (len(cases) != 432 or len(metadata) != len(cases) or result.get('qualified') is not True or
            result.get('fixed_policy') != {'rolling': 3, 'threshold': .9} or
            any(any(a[k] != b[k] for k in keys) for a, b in zip(cases, metadata)) or
            [r['factor'] for r in result['factors']] != [1.15, 1.3, 1.5]):
        raise ValueError('Complete unchanged tempo DEV trace evidence required')
    for factor, saved in zip((1.15, 1.3, 1.5), result['factors']):
        part = [c for c in cases if c['tempo_factor'] == factor]
        historical = policy_metrics(part, 3, .9)
        heard = policy_metrics(reviewed_cohorts(part, review), 3, .9)
        if (len(part) != 144 or historical != saved['historical_groups'] or
                heard != saved['reviewed_groups'] or not historical['passed'] or not heard['passed'] or
                saved.get('positive_shortfall') != 0 or saved.get('qualified') is not True):
            raise ValueError('Tempo DEV pass is not supported by native traces')


def secondary_spec(plan, result):
    profiles = plan.get('profiles', [])
    matches = [p for p in profiles if p['name'] == result.get('profile')]
    if any(p.get('required_secondary_negative_dev') for p in profiles) and len(matches) != 1:
        raise ValueError('Candidate profile cannot bypass required secondary DEV')
    return matches[0].get('required_secondary_negative_dev') if matches else None


def finalize(experiment, baseline, prepared, micro, review_path, isolation_path, output):
    frozen_path = experiment/'frozen.json'
    frozen = json.loads(frozen_path.read_text())
    baseline_proof = json.loads((baseline/'provenance.json').read_text())
    result = validate_gate(frozen, json.loads(review_path.read_text()), baseline_proof['manifest_sha256'])
    from wake_test_isolation import validate as validate_isolation
    isolation = json.loads(isolation_path.read_text())
    validate_isolation(isolation, [Path(p) for p in isolation['source_manifests_sha256']])
    if baseline_proof['manifest_sha256'] not in isolation['source_manifests_sha256'].values():
        raise ValueError('Fresh TEST isolation must cover this original TRAIN/DEV corpus')
    checkpoint = (experiment/frozen['checkpoint']).resolve()
    if not checkpoint.is_relative_to(experiment.resolve()):
        raise ValueError('Frozen checkpoint escapes experiment')
    model = checkpoint/'hi_pikoo.tflite'
    if (sha(model) != frozen['model_sha256'] or sha(model) != result['static']['sha256'] or
            sha(micro) != result['micro_sha256'] or
            result.get('host_arena_bytes', 262145) > 262144):
        raise ValueError('Frozen model, native backend or resource evidence changed')
    evaluation = json.loads((checkpoint/'evaluation.json').read_text())
    for key in ('old_DEV', 'new_negative_DEV_false_clips', 'new_negative_DEV_cases', 'static',
                'rolling', 'threshold'):
        if evaluation[key] != result[key]:
            raise ValueError('Frozen evaluation differs from source checkpoint')
    for key in ('reviewed_DEV', 'reviewed_DEV_gate_passed', 'reviewed_DEV_required_group_hits'):
        if evaluation.get(key) != result.get(key):
            raise ValueError('Reviewed DEV evidence differs from source checkpoint')
    cases = json.loads((checkpoint/'old-dev-cases.json').read_text())
    negatives = json.loads((checkpoint/'negative-dev-scores.json').read_text())
    plan = json.loads((experiment/'plan.json').read_text())
    verify_saved_dev(cases, negatives, result, frozen['policy'], plan)
    preservation_base = json.loads((prepared/'old-dev-cases.json').read_text())
    if plan.get('current_candidate_DEV_preservation'):
        preservation = plan['current_candidate_DEV_preservation']
        donor_cases = experiment/'preservation-dev-cases.json'
        donor_proof = experiment/'preservation-dev-evaluation.json'
        if (sha(donor_cases) != preservation['cases_sha256'] or
                sha(donor_proof) != preservation['evaluation_sha256']):
            raise ValueError('Declared preservation baseline changed')
        proof = json.loads(donor_proof.read_text())
        if proof['static']['sha256'] != preservation['baseline_model_sha256']:
            raise ValueError('Preservation baseline model differs')
        from wake_tempo import preservation_cases
        preservation_base = preservation_cases(preservation_base, json.loads(donor_cases.read_text()), proof)
        import math
        required = {g: max(v['hits'], math.ceil(.9*v['targets'])) for g, v in proof['old_DEV']['groups'].items()}
        if result['required_group_hits'] != required:
            raise ValueError('Current candidate preservation floor was relaxed')
    if plan.get('DEV_content_review_sha256') or 'reviewed_DEV' in result:
        if plan.get('DEV_content_review_sha256') != sha(review_path):
            raise ValueError('Declared human content review differs')
        from wake_dev_content_review import verify_reviewed_gate
        verify_reviewed_gate(cases, preservation_base,
                             json.loads(review_path.read_text()), result, frozen['policy'])
    if plan.get('pitch_preserving_tempo'):
        tempo = experiment/'tempo'
        proof = json.loads((tempo/'provenance.json').read_text())
        if proof != plan['pitch_preserving_tempo']:
            raise ValueError('Tempo preparation provenance differs')
        for name, digest in proof['files_sha256'].items():
            if Path(name).name != name or sha(tempo/name) != digest:
                raise ValueError('Tempo preparation changed')
        if result.get('tempo_DEV') != evaluation.get('tempo_DEV'):
            raise ValueError('Frozen tempo evaluation differs from source')
        verify_tempo(json.loads((checkpoint/'tempo-dev-cases.json').read_text()),
            json.loads((tempo/'dev-metadata.json').read_text()), result['tempo_DEV'], json.loads(review_path.read_text()))
    secondary = None
    spec = secondary_spec(plan, result)
    if spec is not None:
        if spec['source_manifest_sha256'] not in isolation['source_manifests_sha256'].values():
            raise ValueError('Fresh TEST isolation must cover secondary DEV too')
        train_speakers = set()
        for path in isolation['source_manifests_sha256']:
            for row in json.loads(Path(path).read_text()):
                if row.get('split') == 'train':
                    train_speakers.add(row.get('speaker'))
        from wake_secondary_dev import evaluate as evaluate_secondary
        secondary = evaluate_secondary(model, micro, spec, checkpoint, train_speakers=train_speakers)
    if (plan.get('TRAIN_extra_sources') and
            plan['TRAIN_extra_sources']['manifest_sha256'] not in isolation['source_manifests_sha256'].values()):
        raise ValueError('Fresh TEST isolation must cover the extra TRAIN source manifest too')
    if sha(prepared/'provenance.json') != plan['prepared_provenance_sha256']:
        raise ValueError('TRAIN fixture provenance differs')
    preparation = json.loads((prepared/'provenance.json').read_text())
    for name in ('train_x.npy', 'train_y.npy', 'train_w.npy'):
        if sha(prepared/name) != preparation['prepared_sha256'][name]:
            raise ValueError('TRAIN fixture array changed')
    x, y, w = [np.load(prepared/name, mmap_mode='r') for name in ('train_x.npy', 'train_y.npy', 'train_w.npy')]
    # New appended sources are TRAIN too, but the cache-only parity fixtures
    # must map to actual retained BASE indices, not beyond the cached array.
    available = base_representatives(plan, len(x))
    selected = []
    for label in (False, True):
        part = sorted({i for i in available if bool(y[i].max() > .5) == label})
        if len(part) < 4:
            raise ValueError('Balanced retained TRAIN-only parity fixtures required')
        selected.extend(part[i] for i in np.linspace(0, len(part)-1, 4).astype(int))
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(model, output/'hi_pikoo.tflite')
    evidence = []
    for index in selected:
        steps = int(np.flatnonzero(w[index] > 0)[-1])+1
        evidence.append({'original_TRAIN_feature_index': index, 'label': bool(y[index].max() > .5),
            **parity(model, micro, x[index, :steps*3], output/f'train-{index}.int8')})
    proof = {'model_sha256': sha(model), 'micro_sha256': sha(micro), 'fixtures': evidence,
        'passed': all(c['byte_exact'] and c['host_arena_bytes'] <= 262144 for c in evidence),
        'scope': 'TRAIN-only builtin reference vs native Micro; host resource evidence',
        'TEST_opened': False, 'household_used': False, 'hardware_accepted': False}
    (output/'micro-parity.json').write_text(json.dumps(proof, indent=2)+'\n')
    if not proof['passed']:
        raise ValueError('Reference/native parity failed; no qualified policy emitted')
    import sys
    sys.path.insert(0, str(Path(__file__).parents[1]/'tools'))
    from check_wake_policy import frontend_fingerprint, validate
    policy = {'schema_version': 1, 'target': 'hi-piku-piko-v2', 'accepted_names': ['piku', 'piko'],
        'model_sha256': sha(model), **frozen['policy'],
        'candidate_frozen_at': datetime.datetime.fromtimestamp(frozen_path.stat().st_mtime, datetime.timezone.utc).isoformat(),
        'development_passed': True, 'development_qualified': True, 'formal_goal_passed': False,
        'frontend_fingerprint': frontend_fingerprint(),
        'frontend': {'sample_rate': 16000, 'feature_bins': 40, 'window_ms': 30,
                     'feature_step_ms': 10, 'inference_step_ms': 30},
        'source_native_freeze_sha256': sha(frozen_path), 'source_report_sha256': sha(checkpoint/'evaluation.json'),
        'source_training_plan_sha256': sha(experiment/'plan.json'),
        'micro_proof_sha256': sha(output/'micro-parity.json'), 'content_review_sha256': sha(review_path),
        'test_isolation_sha256': sha(isolation_path),
        'required_test_cohorts': sorted(result['old_DEV']['groups']),
        'required_fresh_test_speakers': isolation['reserved_source_speakers'],
        'forbidden_test_speakers': isolation['used_source_speakers'],
        'status': 'DEV-qualified-awaiting-fresh-TEST', 'sealed_test_passed': False,
        'esp32_resource_accepted': False, 'real_child_accepted': False, 'release_eligible': False}
    if secondary is not None:
        policy['secondary_negative_DEV_passed'] = True
        policy['secondary_negative_DEV_report_sha256'] = sha(checkpoint/'secondary-negative-dev-report.json')
    validate(output/'hi_pikoo.tflite', policy)
    (output/'wake-policy.json').write_text(json.dumps(policy, indent=2)+'\n')
    return policy


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('experiment', 'baseline', 'prepared', 'micro', 'review', 'test-isolation', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    os.umask(0o077)
    policy = finalize(a.experiment, a.baseline, a.prepared, a.micro, a.review, a.test_isolation, a.output)
    print(json.dumps({'status': policy['status'], 'model_sha256': policy['model_sha256'],
                      'TEST_opened': False, 'device_changed': False}))


if __name__ == '__main__': main()
