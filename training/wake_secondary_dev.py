# SPDX-License-Identifier: Apache-2.0
"""Pinned unsupported-greeting DEV guard before candidate finalization.

Legacy synthetic validation stays validation, not new independent TEST. ASR
screens are content evidence, never human/phoneme or real-child acceptance.
"""
import hashlib
import json
from pathlib import Path
import tempfile

import numpy as np
from hi_pikoo_review import normalized, content_match
from hi_pikoo_model import event_scores


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def complete_nihao(text):
    text = normalized(text.translate({0x8932: 0x88e4}))
    if not text.startswith('你好'):
        return False
    suffix = text[2:]
    return suffix in {'piku', 'pikoo', 'piko'} or content_match(
        {'label': 1, 'target_contract': 'hi-piku-piko-v2'}, '嗨'+suffix)


def load(spec, train_speakers=()):
    paths = {}
    for name in ('features', 'cases', 'protocol', 'content_review', 'protected', 'source_manifest'):
        path = Path(spec[name])
        if sha(path) != spec[name+'_sha256']:
            raise ValueError('Secondary DEV input changed: '+name)
        paths[name] = path
    protocol = json.loads(paths['protocol'].read_text())
    cases = json.loads(paths['cases'].read_text())
    reviews = {r['source_sha256']: r for r in json.loads(paths['content_review'].read_text())}
    protected = set(json.loads(paths['protected'].read_text()))
    sources = protocol['source_sha256']
    manifest = json.loads(paths['source_manifest'].read_text())
    if (protocol.get('household_used') is not False or protocol.get('TEST_opened') is not False or
            protocol.get('selection') != 'all four original validation files passing content screens, no KWS-score selection' or
            protocol.get('speeds') != [1., 1.15, 1.3, 1.5] or len(sources) != 4 or len(set(sources)) != 4 or
            protocol.get('fixed_policy') != {'rolling': 3, 'threshold': .9} or len(cases) != 16):
        raise ValueError('Complete predeclared reused DEV required')
    if ({r['sha256'] for r in manifest} != set(sources) or len(manifest) != 4 or
            any(r.get('split') != 'validation' or r.get('label') != 0 or r.get('historical_label') != 1 or
                not r.get('synthetic') or any(r.get(k) for k in ('real_child', 'family_inputs_used',
                    'reference_audio_used', 'evaluation_only', 'frozen_holdout')) for r in manifest)):
        raise ValueError('Original synthetic DEV identity and new negative role required')
    for source in sources:
        review = reviews[source]
        source_row = next(r for r in manifest if r['sha256'] == source)
        if (source in protected or review.get('original_split') != 'validation' or
                review.get('original_speaker') in train_speakers or review.get('prior_approved') is not True or
                source_row['speaker'] != review.get('original_speaker') or
                review.get('v3_screen_agreement') is not True or
                not complete_nihao(review['prior_transcript']) or not complete_nihao(review['local_transcript'])):
            raise ValueError('Protected, cross-partition or unreviewed secondary DEV')
    expected = [(s, speed) for s in sources for speed in protocol['speeds']]
    if [(c['source_sha256'], c['speed']) for c in cases] != expected:
        raise ValueError('Secondary DEV source/speed cases omitted or reordered')
    with np.load(paths['features']) as data:
        if set(data.files) != {f'case_{i}' for i in range(16)}:
            raise ValueError('Complete secondary feature cache required')
        features = [data[f'case_{i}'].copy() for i in range(16)]
    for feat, case in zip(features, cases):
        if (case.get('original_split') != 'validation' or case.get('historical_label') != 1 or
                case.get('expected_current_contract_label') != 0 or case.get('whole_original_waveform_used') is not True or
                feat.ndim != 2 or feat.shape[1] != 40 or len(feat) % 3 or not np.isfinite(feat).all() or
                len(case['times_ms']) != len(feat)//3 or len(feat) < 9):
            raise ValueError('Secondary DEV labels/frontend differ')
    return features, cases


def evaluate(model, micro, spec, output, train_speakers=(), evaluator=None):
    features, cases = load(spec, train_speakers)
    if evaluator is None:
        from wake_int8_iterate import NativeEvaluator
        evaluator = NativeEvaluator(micro)
    evaluator.configure(model)
    scored = []
    with tempfile.TemporaryDirectory(dir=output) as tmp:
        for feat, meta in zip(features, cases):
            probabilities, arena = evaluator.run(feat, Path(tmp))
            scores = event_scores(probabilities, 3)
            if arena > 262144:
                raise ValueError('Secondary DEV host arena budget exceeded')
            scored.append({k: v for k, v in meta.items() if not k.startswith('baseline_')} | {
                'probabilities': probabilities.tolist(), 'peak': float(scores.max()),
                'false_wake': bool(np.any(scores >= .9))})
    report = {'scope': 'supplemental reused synthetic DEV, not independent TEST',
        'model_sha256': sha(model), 'micro_sha256': sha(micro), 'cases': len(scored),
        'false_wakes': sum(c['false_wake'] for c in scored),
        'fixed_policy': {'rolling': 3, 'threshold': .9}, 'household_used': False,
        'TEST_opened': False, 'native_reset_replays': 3, 'source_spec': spec}
    (output/'secondary-negative-dev-traces.json').write_text(json.dumps(scored)+'\n')
    (output/'secondary-negative-dev-report.json').write_text(json.dumps(report, indent=2)+'\n')
    if report['false_wakes']:
        raise ValueError('Unsupported greeting false wake; candidate cannot be finalized')
    return report
