#!/usr/bin/env python3
"""Prove a supplied class checkpoint's causal graph before fitting it.

Requires existing, authorized data/checkpoint and the pinned upstream checkout.
No downloads, deployment, household input, or accuracy claims are performed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import numpy as np


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('upstream', 'manifest', 'checkpoint', 'protected-hashes', 'output'):
        p.add_argument('--'+name, required=True, type=Path)
    p.add_argument('--short-context', action='store_true', help='Prove the experimental ordered acoustic branch')
    p.add_argument('--raw-branch', action='store_true', help='Use a separate trainable96-filter raw projection')
    a = p.parse_args()
    if a.raw_branch and not a.short_context:
        raise ValueError('Raw projection requires the explicit short-context architecture')
    os.umask(0o077)
    os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
    sys.path.insert(0, str(a.upstream.resolve()))
    import tensorflow as tf
    from microwakeword import mixednet
    from train import load
    from contrastive_readout import attach, resume_readout, attach_frozen_residual
    from causal_data import training_rows, example
    from causal_model import sequence_view, scalar_view, streaming, replay
    from speech_context import SpeechContext
    from check_esp32_model import check
    tf.keras.utils.set_random_seed(42)
    tf.config.threading.set_intra_op_parallelism_threads(2)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    protected = set(json.loads(a.protected_hashes.read_text())['audio_sha256'].values())
    rows = training_rows(json.loads(a.manifest.read_text()), a.manifest.parent, protected)
    chosen = []
    for label in (0, 1):
        pool = {row['sha256']: row for row in rows if row['label'] == label}
        if len(pool) < 4:
            raise ValueError('Four distinct TRAIN examples per binary class required')
        chosen.extend(pool[digest] for digest in sorted(pool)[:4])
    background = SpeechContext(rows, a.manifest.parent, 43)
    features = [example(load(a.manifest.parent/row['path']), row, np.random.default_rng(100+i),
                background if i % 2 else None)[0] for i, row in enumerate(chosen)]
    flags = SimpleNamespace(pointwise_filters=','.join(['128']*6), repeat_in_block=','.join(['1']*6),
        mixconv_kernel_sizes='[5],[9],[13],[21],[31],[43]', residual_connection=','.join(['0']*6),
        first_conv_filters=64, first_conv_kernel_size=3, stride=3, spatial_attention=0, pooled=1, max_pool=0)
    source, view = attach(mixednet.model(flags, (399, 40), None), warm_start=True)
    proof = resume_readout(source, view, a.checkpoint, np.asarray(features)[:2, -399:],
        {'filters': 128, 'first_filters': 64, 'kernels': [5, 9, 13, 21, 31, 43]})
    if a.short_context:
        from causal_branch import attach as attach_branch
        sequence, graph = attach_branch(source, 600, raw_filters=96 if a.raw_branch else 0)
    else:
        residual, _ = attach_frozen_residual(source, 64)
        sequence, graph = sequence_view(residual, 600)
    wake = scalar_view(sequence)
    report = {'scope': 'TRAIN-only prototype, not accuracy or deployment acceptance',
        'source': proof, 'graph': graph, 'cases': [], 'household_or_development_used': False,
        'causal_model_sha256': hashlib.sha256(Path(__file__).with_name('causal_model.py').read_bytes()).hexdigest()}
    if a.short_context:
        report['causal_branch_sha256'] = hashlib.sha256(Path(__file__).with_name('causal_branch.py').read_bytes()).hexdigest()
    a.output.mkdir(parents=True, exist_ok=False)
    for row, feature in zip(chosen, features):
        original = replay(streaming(source), feature)
        batch = sequence(feature[None], training=False).numpy()[0]
        step = replay(streaming(sequence), feature)
        scalar = replay(streaming(wake), feature)[:, 0]
        error = float(max(np.max(abs(original-batch)), np.max(abs(original-step)), np.max(abs(original[:, 1]-scalar))))
        report['cases'].append({'train_sha256': row['sha256'], 'label': row['label'],
                                'steps': 200, 'all_class_max_difference': error})
        print(json.dumps({'completed_cases': len(report['cases']), 'all_class_max_difference': error}), flush=True)
        if error > 1e-5:
            raise ValueError('Original and causal all-step probabilities differ')
    report['status'] = 'all-step-float-parity-passed-static-export-pending'
    (a.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    if a.short_context:
        from causal_branch import integer_anchor
        exported = integer_anchor(sequence)
        for feature in features:
            if np.max(abs(exported(feature[None], training=False).numpy()-sequence(feature[None], training=False).numpy())) > 1e-5:
                raise ValueError('Integer-state anchor changed float probabilities')
        model = streaming(scalar_view(exported))
    else:
        model = streaming(wake)
    archive = tf.keras.export.ExportArchive()
    archive.track(model)
    archive.add_endpoint(name='serve', fn=model.call, input_signature=[tf.TensorSpec(model.input.shape, tf.float32)])
    archive.write_out(str(a.output/'saved'), verbose=False)

    def representative():
        for feature in features:
            for offset in range(0, 600, 3):
                yield [feature[None, offset:offset+3].astype(np.float32)]

    converter = tf.lite.TFLiteConverter.from_saved_model(str(a.output/'saved'))
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter._experimental_variable_quantization = True
    converter._experimental_disable_per_channel_quantization_for_dense_layers = True
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type, converter.inference_output_type = tf.int8, tf.uint8
    converter.representative_dataset = representative
    path = a.output/'nihao_pikoo.tflite'
    path.write_bytes(converter.convert())
    try:
        compatibility = check(path, Path(__file__).parents[1]/'firmware/main/wake_model.cpp', 524288)
    except ValueError as error:
        report.update(status='failed-static-export', error=str(error))
        (a.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
        raise
    report.update(static=compatibility,
        model_bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        inference_input_shape=list(model.input.shape), inference_output_shape=list(model.output.shape),
        status='all-step-float-parity-and-static-export-passed-not-trained-or-flashed',
        trained=False, device_modified=False)
    (a.output/'report.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
