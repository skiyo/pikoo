#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Correct a noisy synthetic DEV endpoint without changing audio/model/splits.

Original reports remain failed and intact. This is reused DEV for measurement
correction, never a new TEST, household test or model retraining result.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from hi_pikoo_train import admit, read_audio, speech_endpoint
from hi_pikoo_model import select_policy


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('comparison', 'manifest', 'protected-hashes', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    protected = set(json.loads(a.protected_hashes.read_text())['audio_sha256'].values())
    rows = json.loads(a.manifest.read_text())
    admitted = admit(rows, a.manifest.parent, protected)
    waveforms = {r['sha256']: path for r, path in admitted if r['split'] == 'validation'}
    provenance = json.loads((a.comparison/'provenance.json').read_text())
    previous = a.comparison/'source-snapshot/hi_pikoo_train.py'
    if sha(previous) != provenance['data_source_sha256']:
        raise ValueError('Original event-clock source snapshot is required')
    spec = importlib.util.spec_from_file_location('previous_training_clock', previous)
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    timing_snapshot = previous.with_name('hi_pikoo_timing.py')
    if timing_snapshot.exists():
        timing_spec = importlib.util.spec_from_file_location('previous_synthetic_timing', timing_snapshot)
        old_timing = importlib.util.module_from_spec(timing_spec)
        timing_spec.loader.exec_module(old_timing)
        old.timing = old_timing.timing
    reports = json.loads((a.comparison/'comparison.json').read_text())
    if len(reports) != 4:
        raise ValueError('Complete original comparison required')
    os.umask(0o077)
    a.output.mkdir(parents=True, exist_ok=False)
    for name in ('features.npz', 'target-contract.json'):
        os.link(a.comparison/name, a.output/name)
    derived = []
    corrections = []
    for report in reports:
        name = f'context-{report["context_steps"]}-seed-{report["seed"]}'
        source, target = a.comparison/name, a.output/name
        target.mkdir()
        if sha(source/'hi_pikoo.tflite') != report['static']['sha256']:
            raise ValueError('Trained model changed')
        os.link(source/'hi_pikoo.tflite', target/'hi_pikoo.tflite')
        cases = json.loads((source/'dev-cases.json').read_text())
        for case in cases:
            if case['label']:
                pcm = read_audio(waveforms[case['sha256']])
                delta = (speech_endpoint(pcm)-old.speech_endpoint(pcm))/16
                case.update(prior_completion_ms=case['completion_ms'],
                    completion_ms=case['completion_ms']+delta,
                    endpoint_method='synthetic-RMS20ms-peakMinus26dB-plus40ms-guard')
                corrections.append({'model': name, 'waveform_sha256': case['sha256'], 'delta_ms': delta})
        revised = {**report, 'development_original_clock': report['development'],
            'development': select_policy(cases), 'original_report_sha256': sha(source/'report.json'),
            'measurement_correction': 'same DEV and unchanged trained weights; quiet synthetic tail excluded',
            'new_test': False, 'retrained': False}
        (target/'dev-cases.json').write_text(json.dumps(cases)+'\n')
        (target/'report.json').write_text(json.dumps(revised, indent=2)+'\n')
        derived.append(revised)
    (a.output/'comparison.json').write_text(json.dumps(derived, indent=2)+'\n')
    (a.output/'measurement-provenance.json').write_text(json.dumps({
        'original_comparison_sha256': sha(a.comparison/'comparison.json'),
        'current_endpoint_source_sha256': sha(Path(__file__).with_name('hi_pikoo_train.py')),
        'corrections': corrections, 'audio_or_models_changed': False,
        'household_used': False, 'new_test': False}, indent=2)+'\n')
    print(json.dumps({'status': 'DEV-measurement-corrected-not-new-test', 'candidates': len(derived)}))


if __name__ == '__main__':
    main()
