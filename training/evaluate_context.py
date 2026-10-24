#!/usr/bin/env python3
"""Development diagnostic: wake words after continuous non-target speech.

This does not train, choose a threshold, open household audio, or score a test
split. Prefixes are concatenated speech, not speech mixed over the target.
"""
import os
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
import argparse
import hashlib
import json
import wave
from pathlib import Path


def eligible(rows, include_non_targets=False):
    if any(r.get('evaluation_only') or r.get('frozen_holdout') or
           str(r.get('source', '')).startswith('private-') for r in rows):
        raise ValueError('Household/held-out input is excluded from development diagnostics')
    return [r for r in rows if r['split'] == 'validation' and
            (include_non_targets or r['label'] == 1)]


def load(row, root, protected):
    path = (root / row['path']).resolve()
    binary = path.read_bytes()
    digest = hashlib.sha256(binary).hexdigest()
    if digest in protected:
        raise ValueError('Protected audio is excluded, including renamed copies')
    if digest != row['sha256']:
        raise ValueError('Recording hash does not match manifest')
    import numpy as np
    with wave.open(str(path)) as stream:
        if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) != (1, 2, 16000):
            raise ValueError('Expected mono PCM16/16kHz')
        return np.frombuffer(stream.readframes(stream.getnframes()), '<i2').copy()


def score(model, prefix, target):
    import numpy as np
    from pymicro_features import MicroFrontend
    from streaming_runtime import interpreter, quantize
    runtime = interpreter(model)
    runtime.allocate_tensors()
    inp = runtime.get_input_details()[0]
    out = runtime.get_output_details()[0]
    if inp['shape'].tolist() != [1, 3, 40]:
        raise ValueError('Expected streaming [1,3,40] input')
    frontend = MicroFrontend()
    pcm = np.concatenate([prefix, target, np.zeros(16000, dtype='<i2')])
    pending, probabilities = [], []
    before, during = [], []
    for pos in range(0, len(pcm) - 159, 160):
        frame = frontend.process_samples(pcm[pos:pos + 160].tobytes())
        if not frame.features:
            continue
        pending.append(frame.features)
        if len(pending) != 3:
            continue
        runtime.set_tensor(inp['index'], quantize(pending, *inp['quantization'])[None, ...])
        pending.clear()
        runtime.invoke()
        probabilities.append((int(runtime.get_tensor(out['index']).flat[0]) -
                              out['quantization'][1]) * out['quantization'][0])
        if len(probabilities) < 5:
            continue
        value = sum(probabilities[-5:]) / 5
        if pos + 160 <= len(prefix):
            before.append(value)
        # Exclude five-score windows crossing the prefix/target boundary.
        elif pos + 160 >= len(prefix) + 2400:
            during.append(value)
    return {'target_peak': max(during, default=0.),
            'prefix_peak': max(before, default=0.),
            'prefix_above_threshold_windows': sum(v >= .9 for v in before)}


def summarize(cases):
    result = {}
    for case in cases:
        key = case['style'] + '/' + case['condition']
        group = result.setdefault(key, {'targets': 0, 'hits': 0,
                                       'prefix_above_threshold_windows': 0})
        if case.get('label', 1):
            group['targets'] += 1
            group['hits'] += int(case['target_peak'] >= .9)
        else:
            group['non_targets'] = group.get('non_targets', 0) + 1
            group['false_wakes'] = group.get('false_wakes', 0) + int(case['target_peak'] >= .9)
        group['prefix_above_threshold_windows'] += case['prefix_above_threshold_windows']
    return result


def main():
    import numpy as np
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', type=Path, required=True)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--protected-hashes', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--prefix-seconds', type=float, default=30.)
    p.add_argument('--prefix-split', choices=['train', 'validation'], default='train')
    p.add_argument('--gaps', default='0,0.3,1')
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--include-non-targets', action='store_true',
                   help='Also score all validation non-target segments after the same prefixes')
    a = p.parse_args()
    gaps = [float(g) for g in a.gaps.split(',')]
    if not .1 <= a.prefix_seconds <= 120 or not gaps or any(not 0 <= g <= 5 for g in gaps):
        p.error('Prefix must be 0.1..120s and gaps 0..5s')
    os.umask(0o077)
    rows = json.loads(a.manifest.read_text())
    targets = eligible(rows, a.include_non_targets)
    pool = [r for r in rows if r['split'] == a.prefix_split and r['label'] == 0]
    if not targets or not pool:
        raise ValueError('Validation targets and non-target prefix recordings are required')
    protected = set(json.loads(a.protected_hashes.read_text())['audio_sha256'].values())
    rng = np.random.default_rng(a.seed)
    pool = [pool[i] for i in rng.permutation(len(pool))]
    parts, used = [], []
    count = 0
    for row in pool:
        pcm = load(row, a.manifest.parent, protected)
        parts.append(pcm)
        used.append(row['sha256'])
        count += len(pcm)
        if count >= round(a.prefix_seconds * 16000):
            break
    if count < round(a.prefix_seconds * 16000):
        raise ValueError('Not enough prefix audio; do not silently repeat recordings')
    prefix = np.concatenate(parts)[:round(a.prefix_seconds * 16000)]
    report = {'status': 'development-diagnostic-not-independent-or-hardware-acceptance',
              'completed': False,
              'threshold': .9, 'rolling_inferences': 5, 'seed': a.seed,
              'model_sha256': hashlib.sha256(a.model.read_bytes()).hexdigest(),
              'manifest_sha256': hashlib.sha256(a.manifest.read_bytes()).hexdigest(),
              'prefix_split': a.prefix_split, 'prefix_seconds': a.prefix_seconds,
              'prefix_recording_sha256': used, 'gaps_seconds': gaps,
              'prefix_shared_across_targets': True,
              'includes_validation_non_targets': a.include_non_targets,
              'target_audio': 'synthetic and/or manifest-declared development audio; not real-child acceptance',
              'cases': []}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    for row in targets:
        target = load(row, a.manifest.parent, protected)
        conditions = [('cold', np.zeros(16000, dtype='<i2'))] + [
            (f'speech-gap-{gap:g}s', np.concatenate([prefix, np.zeros(round(gap * 16000), dtype='<i2')]))
            for gap in gaps]
        for name, context in conditions:
            item = score(a.model, context, target)
            item.update(condition=name, style=row.get('synthetic_style', 'unspecified'),
                        source=row.get('source', 'unspecified'), target_sha256=row['sha256'],
                        label=row['label'])
            report['cases'].append(item)
        report['summary'] = summarize(report['cases'])
        a.output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({'targets_scored': len(report['cases']) // len(conditions),
                          'total_targets': len(targets)}), flush=True)
    report['completed'] = True
    a.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['summary']), flush=True)


if __name__ == '__main__':
    main()
