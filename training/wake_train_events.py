#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Recover phrase-family TRAIN timing only after exact cached-array replay.

Original inputs and every replayed feature/label/weight must match. This never
reads DEV waveforms, TEST or household recordings, or edits cached training.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

import numpy as np


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_example(cached, generated, index):
    for name, old, new in zip(('features', 'labels', 'weights'), cached, generated):
        if old.shape != new.shape or old.dtype != new.dtype or old.tobytes() != new.tobytes():
            raise ValueError(f'Original TRAIN {name} replay differs at index {index}')


def recover(manifest, background, protected, baseline, output):
    if output.exists():
        raise ValueError('Do not overwrite a recovered TRAIN event archive')
    provenance = json.loads((baseline/'provenance.json').read_text())
    if (provenance.get('household_used') is not False or
            provenance.get('sealed_test_opened') is not False or
            digest(manifest) != provenance['manifest_sha256'] or
            digest(background) != provenance['background_manifest_sha256']):
        raise ValueError('Audited original TRAIN inputs required')
    original_source = baseline/'source-snapshot/hi_pikoo_train.py'
    if digest(original_source) != provenance['data_source_sha256']:
        raise ValueError('Original preparation snapshot does not match its provenance')
    # Replaying today's preparation can change old padding/timing semantics.
    # Load the authenticated original version, then require exact array equality.
    sys.path.insert(0, str(original_source.parent))
    spec = importlib.util.spec_from_file_location('original_pikoo_preparation', original_source)
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    from hi_pikoo_contrast import family
    background_rows, example, read_audio = original.background_rows, original.example, original.read_audio
    protected_hashes = set(json.loads(protected.read_text())['audio_sha256'].values())
    rows = json.loads(manifest.read_text())
    # Inspect all split metadata for leakage, but never load DEV audio here.
    for row in rows:
        if row['split'] not in ('train', 'validation'):
            raise ValueError('TEST cannot appear in this invocation')
    training = [r for r in rows if r['split'] == 'train']
    # admit() requires both declared splits; perform its per-row validation
    # without touching DEV waveforms by validating original TRAIN metadata and
    # paths directly with the shared review boundary.
    from hi_pikoo_review import validate
    selected = []
    for row in training:
        path = validate(row, manifest.parent, protected_hashes)
        if (not row.get('admitted_to_training') or
                row.get('content_review') != 'passed' or
                row.get('pronunciation_review') != 'passed'):
            raise ValueError('Independently admitted synthetic TRAIN required')
        selected.append((row, path))
    backgrounds = background_rows(background, protected_hashes)
    warm_pool = [read_audio(p) for _, p in backgrounds[::max(1, len(backgrounds)//32)][:32]]
    records = []
    with np.load(baseline/'features.npz') as cache:
        x, y, w = (cache[k] for k in ('train_x', 'train_y', 'train_w'))
        for row, path in selected+backgrounds:
            repeats = (12 if row['label'] else 6) if row.get('synthetic') else 1
            pcm = read_audio(path)
            for repeat in range(repeats):
                key = f'20261031/train/{row["sha256"]}/{repeat}'.encode()
                rng = np.random.default_rng(int.from_bytes(hashlib.sha256(key).digest()[:8], 'little'))
                augmented = repeat > 0
                warm = warm_pool[int(rng.integers(len(warm_pool)))] if augmented and warm_pool and rng.random() < .5 else None
                # The original first augmentation draw controls resampling.
                predictor = np.random.default_rng()
                predictor.bit_generator.state = copy.deepcopy(rng.bit_generator.state)
                speed = float(predictor.uniform(.9, 1.1)) if augmented else 1.
                values = example(pcm, row, rng, augment=augmented, background_pcm=warm)
                index = len(records)
                if index >= len(x):
                    raise ValueError('More reconstructed examples than original TRAIN cache')
                verify_example((x[index], y[index], w[index]), values[:3], index)
                meta = {**values[3], 'repeat': repeat, 'contrast_class': family(row)}
                # Binary negatives used the whole file as completion time. A
                # training-only competitor event must follow speech, not a quiet
                # file tail. Full positives retain their original event clock.
                if meta['contrast_class'] > 1:
                    if len(pcm) > 64000 or (augmented and len(pcm)/speed > 64000):
                        raise ValueError('Cropped competitor needs explicit timing review')
                    meta['original_completion_ms'] = meta['completion_ms']
                    meta['completion_ms'] -= (len(pcm)-original.speech_endpoint(pcm))/16/speed
                    meta['auxiliary_clock'] = 'Original speech endpoint, speed and lead; no binary labels changed'
                records.append(meta)
                if index % 500 == 0:
                    print(json.dumps({'verified_TRAIN_examples': index+1}), flush=True)
        if len(records) != len(x):
            raise ValueError('Original TRAIN cache length differs')
    temporary = output.with_suffix('.partial')
    temporary.write_text(json.dumps({'records': records, 'proof': {
        'original_features_sha256': digest(baseline/'features.npz'),
        'manifest_sha256': digest(manifest), 'background_manifest_sha256': digest(background),
        'protected_sha256': digest(protected), 'recovery_source_sha256': digest(Path(__file__)),
        'original_preparation_sha256': digest(original_source),
        'every_original_TRAIN_array_byte_equal': True,
        'household_used': False, 'DEV_waveforms_read': False, 'TEST_opened': False,
        'source_manifest_labels_unchanged': True}}, indent=2)+'\n')
    temporary.replace(output)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'background', 'protected', 'baseline', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    os.umask(0o077)
    recover(a.manifest, a.background, a.protected, a.baseline, a.output)


if __name__ == '__main__':
    main()
