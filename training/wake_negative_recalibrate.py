#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compare two TRAIN-only calibration sets for an unchanged wake checkpoint.

This is development selection, never a threshold change or independent TEST.
No gradient updates, household data, paid calls, or board writes are performed.
"""
import argparse
import json
import os
from pathlib import Path
import numpy as np
from hi_pikoo_model import build, stream, policy_metrics
from hi_pikoo_train import features_and_times, replay
from wake_negative_finetune import recall_preserved
from wake_playback_negatives import load_rows, read_pcm, score, sha, verify_dev


def calibration_sources(rows):
    selected = []
    for source, count in [('ChildMandarin', 16), ('LibriSpeech-train.100', 16), ('ESC-50', 8)]:
        part = sorted([r for r in rows if r['split'] == 'train' and r['source'] == source],
                      key=lambda r: r['sha256'])
        if len(part) < count:
            raise ValueError('Incomplete stratified TRAIN calibration')
        selected.extend(part[i] for i in np.linspace(0, len(part)-1, count).astype(int))
    return selected


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ('checkpoint', 'baseline-run', 'manifest', 'protected-hashes', 'upstream', 'micro', 'output'):
        p.add_argument('--'+flag, type=Path, required=True)
    a = p.parse_args()
    os.umask(0o077)
    rows = load_rows(a.manifest, a.protected_hashes)
    with np.load(a.baseline_run/'features.npz') as cache:
        x, y, w, vx = [cache[k] for k in ('train_x', 'train_y', 'train_w', 'dev_x')]
        labels = cache['train_binary_labels'] if 'train_binary_labels' in cache.files else y.max(axis=1)>0
    info = json.loads((a.baseline_run/'context-20-seed-43/dev-cases.json').read_text())
    protected = set(json.loads(a.protected_hashes.read_text())['audio_sha256'].values())
    if len(info) != len(vx) or any(c['sha256'] in protected for c in info):
        raise ValueError('Protected/incomplete DEV')
    baseline = policy_metrics(info, 3, .9)
    representatives = []
    for label in (0, 1):
        for index in np.flatnonzero(labels == label)[:40]:
            valid = int(np.flatnonzero(w[index] > 0)[-1])+1
            representatives.append(x[index, :valid*3])
    extra_rows = calibration_sources(rows)
    extra = [features_and_times(np.pad(read_pcm(a.manifest.parent/r['path']), (16000, 16000)))[0]
             for r in extra_rows]
    a.output.mkdir(parents=True, exist_ok=False)
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(4)
    tf.config.threading.set_inter_op_parallelism_threads(2)
    checkpoint_hash = sha(a.checkpoint)
    model = build(a.upstream, 20, 43, 24, False)
    model.load_weights(a.checkpoint)
    deploy = stream(model)
    archive = tf.keras.export.ExportArchive()
    archive.track(deploy)
    archive.add_endpoint(name='serve', fn=deploy.call,
                        input_signature=[tf.TensorSpec(deploy.input.shape, tf.float32)])
    archive.write_out(str(a.output/'saved'), verbose=False)
    reports = []
    for mode, arrays in [('original-TRAIN', representatives), ('stratified-TRAIN', representatives+extra)]:
        folder = a.output/mode
        folder.mkdir()
        converter = tf.lite.TFLiteConverter.from_saved_model(str(a.output/'saved'))
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        converter._experimental_variable_quantization = True
        converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
        converter.inference_input_type, converter.inference_output_type = tf.int8, tf.uint8
        converter.representative_dataset = lambda: ([data[None, i:i+3]]
            for data in arrays for i in range(0, len(data)-2, 3))
        target = folder/'hi_pikoo.tflite'
        target.write_bytes(converter.convert())
        from streaming_runtime import interpreter
        cases = [{**meta, 'probabilities': replay(interpreter(target), data)[:meta['valid_steps']]}
                 for data, meta in zip(vx, info)]
        (folder/'dev-cases.json').write_text(json.dumps(cases)+'\n')
        old = policy_metrics(cases, 3, .9)
        verify_dev(target, a.baseline_run/'features.npz', folder/'dev-cases.json',
                   a.protected_hashes, a.micro.resolve(), folder/'native-dev')
        score(a.manifest, a.protected_hashes, target, a.micro.resolve(), folder/'continuous')
        new = json.loads((folder/'continuous/report.json').read_text())['summary']['validation']
        report = {'mode': mode, 'checkpoint_sha256': checkpoint_hash, 'model_sha256': sha(target),
            'model_bytes': target.stat().st_size, 'old_dev': old, 'new_dev': new,
            'old_dev_preserved': recall_preserved(baseline, old),
            'training_calibration_sources': len(arrays), 'new_source_hashes': [r['sha256'] for r in extra_rows] if mode == 'stratified-TRAIN' else [],
            'household_used': False, 'test_opened': False, 'gradient_updates': 0,
            'threshold_changed': False, 'flashed': False}
        (folder/'report.json').write_text(json.dumps(report, indent=2)+'\n')
        reports.append(report)
        (a.output/'comparison.json').write_text(json.dumps(reports, indent=2)+'\n')
    if sha(a.checkpoint) != checkpoint_hash:
        raise ValueError('Checkpoint changed during calibration')


if __name__ == '__main__':
    main()
