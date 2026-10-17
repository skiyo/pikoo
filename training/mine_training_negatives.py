#!/usr/bin/env python3
"""Mine causal false-trigger prefixes from TRAIN only; no household/test input."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import wave

import numpy as np
from pymicro_features import MicroFrontend
from streaming_runtime import interpreter as create_interpreter, quantize
from train import load
from prepare_voice_variants import validate


def peak_prefix(model, pcm):
    engine = create_interpreter(model)
    engine.allocate_tensors()
    input_ = engine.get_input_details()[0]
    output = engine.get_output_details()[0]
    frontend, pending, probabilities = MicroFrontend(), [], []
    samples = np.pad(pcm.astype('<i2'), (16000, 16000))
    best, end = 0., 0
    for offset in range(0, len(samples) - 159, 160):
        result = frontend.process_samples(samples[offset:offset + 160].tobytes())
        if not result.features:
            continue
        pending.append(result.features)
        if len(pending) < 3:
            continue
        engine.set_tensor(input_['index'], quantize(pending, *input_['quantization'])[None, ...])
        pending = []
        engine.invoke()
        scale, zero = output['quantization']
        probabilities.append((int(engine.get_tensor(output['index']).flat[0]) - zero) * scale)
        if len(probabilities) >= 5:
            score = float(np.mean(probabilities[-5:]))
            if score > best:
                best, end = score, min(len(pcm), max(0, offset + 160 - 16000))
    return best, end


def mining_rows(rows):
    return [r for r in rows if r['split'] == 'train' and r['label'] == 0]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--model', type=Path, required=True)
    p.add_argument('--protected-hashes', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--minimum-score', type=float, default=.3)
    p.add_argument('--maximum-clips', type=int, default=200)
    a = p.parse_args()
    os.umask(0o077)
    if not 0 < a.minimum_score < 1 or not 1 <= a.maximum_clips <= 500:
        raise ValueError('Invalid mining bounds')
    rows = json.loads(a.manifest.read_text())
    protected = set(json.loads(a.protected_hashes.read_text())['audio_sha256'].values())
    validate(rows, a.manifest.parent, protected)
    source_hash = hashlib.sha256(a.model.read_bytes()).hexdigest()
    selected, all_negatives = [], mining_rows(rows)
    for n, row in enumerate(all_negatives, 1):
        score, end = peak_prefix(a.model, load(a.manifest.parent / row['path']))
        if score >= a.minimum_score and end >= 4000:
            selected.append((score, end, row))
        if n % 250 == 0:
            print(json.dumps({'training_negatives_scored': n, 'total': len(all_negatives),
                              'above_mining_score': len(selected)}), flush=True)
    assert hashlib.sha256(a.model.read_bytes()).hexdigest() == source_hash
    a.output.mkdir(parents=True, exist_ok=True)
    audio_dir = a.output / 'audio'
    audio_dir.mkdir(exist_ok=True)
    merged = [{**r, 'path': os.path.relpath((a.manifest.parent / r['path']).resolve(), a.output.resolve())}
              for r in rows]
    speakers, mined = Counter(), []
    for score, end, row in sorted(selected, key=lambda x: -x[0]):
        group = row.get('speaker') or row.get('voice') or row['group']
        if speakers[group] >= 4 or len(mined) >= a.maximum_clips:
            continue
        speakers[group] += 1
        pcm = load(a.manifest.parent / row['path'])[:end].astype('<i2')
        name = hashlib.sha256(f"{row['sha256']}:{end}".encode()).hexdigest()
        path = audio_dir / f'{name}.wav'
        with wave.open(str(path), 'wb') as audio:
            audio.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            audio.writeframes(pcm.tobytes())
        mined.append({**row, 'path': str(path.relative_to(a.output)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'hard_negative': True, 'mined_training_prefix': True,
            'mining_model_sha256': source_hash, 'parent_sha256': row['sha256'],
            'causal_end_sample': end, 'development_mining_score': score})
    merged.extend(mined)
    validate(merged, a.output, protected)
    (a.output / 'manifest.json').write_text(json.dumps(merged, ensure_ascii=False, indent=2) + '\n')
    report = {'status': 'training-only-hard-negative-prefixes', 'model_sha256': source_hash,
        'scored_training_negatives': len(all_negatives), 'scored_validation_or_test': 0,
        'minimum_score': a.minimum_score, 'selected_prefixes': len(mined),
        'real_child_prefixes': sum(bool(r.get('real_child')) for r in mined),
        'household_recordings_used': 0}
    (a.output / 'mining-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
