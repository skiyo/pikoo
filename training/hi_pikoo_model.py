#!/usr/bin/env python3
# Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
"""Independent Hi Pikoo causal model; no historical phrase head or weights.

Import has no network, corpus access or training side effects. Both temporal
variants keep the same frontend and stateful [1,3,40] device interface.
"""
import os
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
import argparse
import hashlib
import json
import sys
from pathlib import Path
import numpy as np

FRAMES = 600
SEEDS = (42, 43)
GRID = [(n, t) for n in (3, 5) for t in (.80, .85, .90, .95)]


def sequence_loss(labels, probabilities):
    import tensorflow as tf
    # Keep the time axis: Keras must apply [batch,time] masks, not broadcast
    # a reduced per-utterance loss over every step.
    return tf.keras.losses.binary_crossentropy(labels[..., None], probabilities[..., None])


def build(upstream, ordered_steps=72, seed=42):
    if ordered_steps not in (20, 72):
        raise ValueError('Only predeclared 20/72 step variants are eligible')
    sys.path.insert(0, str(Path(upstream).resolve()))
    import tensorflow as tf
    from microwakeword.layers.stream import Stream
    tf.keras.utils.set_random_seed(seed)
    inputs = tf.keras.Input((FRAMES, 40), name='features')
    x = tf.keras.layers.Reshape((-1, 1, 40))(inputs)
    # Physical microfrontend units remain unchanged at the device boundary.
    # Scale inside the model so initial ReLU6 projections do not discard the
    # fine spectral differences between p/t on these ~0..26-valued features.
    x = tf.keras.layers.Rescaling(1/26., name='frontend_scale')(x)
    x = Stream(tf.keras.layers.Conv2D(96, (3, 1), strides=(3, 1),
        activation='relu6', use_bias=False, kernel_initializer='he_normal'), use_one_step=False,
        pad_time_dim='causal', name='input_projection')(x)
    for i, width in enumerate((5, 9, 13)):
        x = Stream(tf.keras.layers.Identity(), ring_buffer_size_in_time_dim=width-1,
            use_one_step=False, pad_time_dim='causal', name=f'context_{i}')(x)
        # A depthwise filter sees width samples of ONE channel, not all input
        # channels. Use its actual fan-in rather than a dense-kernel fan-in.
        x = tf.keras.layers.DepthwiseConv2D((width, 1), use_bias=False,
            depthwise_initializer=tf.keras.initializers.RandomNormal(stddev=np.sqrt(2/width)))(x)
        x = tf.keras.layers.Conv2D(24, 1, activation='relu6',
            kernel_initializer='he_normal', name=f'mix_{i}')(x)
    x = Stream(tf.keras.layers.Identity(), ring_buffer_size_in_time_dim=ordered_steps-1,
        use_one_step=False, pad_time_dim='causal', name='ordered_context')(x)
    x = tf.keras.layers.DepthwiseConv2D((ordered_steps, 1), activation='relu6',
        depthwise_initializer=tf.keras.initializers.RandomNormal(stddev=np.sqrt(2/ordered_steps)))(x)
    x = tf.keras.layers.Conv2D(32, 1, activation='relu6', kernel_initializer='he_normal')(x)
    x = tf.keras.layers.Conv2D(1, 1, activation='sigmoid',
        bias_initializer=tf.keras.initializers.Constant(-3), name='wake_probability')(x)
    return tf.keras.Model(inputs, tf.keras.layers.Reshape((-1,))(x))


def stream(model):
    import tensorflow as tf
    from microwakeword.layers import modes
    from microwakeword.utils import to_streaming_inference
    # Trained Keras models carry their compile configuration during cloning.
    # Make the temporal loss resolvable without importing TensorFlow at module
    # import time or recompiling the deploy-only clone with a different loss.
    with tf.keras.utils.custom_object_scope({'sequence_loss': sequence_loss}):
        clone = tf.keras.models.clone_model(model)
        clone.set_weights(model.get_weights())
        # Upstream performs another clone inside this conversion.
        return to_streaming_inference(clone,
            {'spectrogram_length': FRAMES, 'feature_bin_count': 40, 'stride': 3},
            modes.Modes.STREAM_INTERNAL_STATE_INFERENCE)


class RollingDecision:
    def __init__(self, rolling):
        if rolling not in (3, 5):
            raise ValueError('Only predeclared smoothing counts are eligible')
        self.ring = np.zeros(rolling, np.float32)
        self.index = self.count = 0

    def feed(self, value):
        self.ring[self.index] = np.float32(value)
        self.index = (self.index+1) % len(self.ring)
        self.count = min(self.count+1, len(self.ring))
        if self.count < len(self.ring):
            return np.float32(0)
        total = np.float32(0)
        for p in self.ring:
            total = np.float32(total+p)
        return total/np.float32(len(self.ring))


def event_scores(probabilities, rolling):
    """Exactly N float32 scores, matching device accumulation order."""
    decision = RollingDecision(rolling)
    return np.asarray([decision.feed(p) for p in probabilities], np.float32)


def select_policy(cases):
    """Reject ANY dev false/early wake before ranking worst cohort recall."""
    results = []
    for rolling, threshold in GRID:
        groups, false_wakes, early, delays = {}, 0, 0, []
        for c in cases:
            scores = event_scores(c['probabilities'], rolling)
            times = np.asarray(c['times_ms'])
            fired = np.flatnonzero(scores >= threshold)
            if not c['label']:
                false_wakes += bool(len(fired))
                continue
            group = c['cohort']
            g = groups.setdefault(group, {'targets': 0, 'hits': 0})
            g['targets'] += 1
            early += bool(np.any(times[fired] < c['completion_ms']-120))
            valid = fired[(times[fired] >= c['completion_ms']-120) &
                          (times[fired] <= c['completion_ms']+800)]
            if len(valid):
                g['hits'] += 1
                delays.append(max(0., float(times[valid[0]]-c['completion_ms'])))
        worst = min((g['hits']/g['targets'] for g in groups.values()), default=0.)
        p95 = float(np.percentile(delays, 95)) if delays else None
        passed = bool(groups) and not false_wakes and not early and worst >= .9 and p95 <= 800
        results.append({'rolling': rolling, 'threshold': threshold, 'groups': groups,
            'false_wakes': false_wakes, 'early_wakes': early, 'worst_recall': worst,
            'latency_p95_ms': p95, 'passed': passed})
    eligible = [x for x in results if x['passed']]
    eligible.sort(key=lambda x: (-x['worst_recall'], x['latency_p95_ms'], -x['threshold'], -x['rolling']))
    return {'status': 'dev-policy-qualified' if eligible else 'dev-rejected',
            'selected': eligible[0] if eligible else None, 'grid': results,
            'human_or_device_acceptance': False}


def development_quality(result):
    """DEV checkpoint proxy only; final INT8 qualification remains mandatory."""
    if result['selected'] is not None:
        return 2.+result['selected']['worst_recall']
    return max((r['worst_recall']-.1*r['false_wakes']-.05*r['early_wakes']
                for r in result['grid']), default=-1.)


def prototype(upstream, output):
    """Finite synthetic numeric check only; not keyword training/acceptance."""
    import tensorflow as tf
    from sequence_export_check import check
    from check_esp32_model import check as static_check
    tf.config.threading.set_intra_op_parallelism_threads(4)
    tf.config.threading.set_inter_op_parallelism_threads(2)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    reports = []
    rng = np.random.default_rng(42)
    fixtures = rng.uniform(0, 20, (8, FRAMES, 40)).astype(np.float32)
    for steps in (20, 72):
        model = build(upstream, steps)
        deploy = stream(model)
        folder = output / f'context-{steps}'
        folder.mkdir(exist_ok=True)
        archive = tf.keras.export.ExportArchive()
        archive.track(deploy)
        archive.add_endpoint(name='serve', fn=deploy.call,
            input_signature=[tf.TensorSpec(deploy.input.shape, tf.float32)])
        archive.write_out(str(folder/'saved'), verbose=False)
        parity = check(model, folder/'saved', fixtures, np.arange(8) % 2)
        if parity['status'] != 'passed-trained-sequence-export-parity':
            raise ValueError('Prototype streaming parity failed')
        converter = tf.lite.TFLiteConverter.from_saved_model(str(folder/'saved'))
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        converter._experimental_variable_quantization = True
        converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
        converter.inference_input_type, converter.inference_output_type = tf.int8, tf.uint8
        # Random synthetic fixtures ONLY for prototype, never final calibration.
        converter.representative_dataset = lambda: ([x[None, i:i+3]]
            for x in fixtures[:2] for i in range(0, FRAMES, 3))
        target = folder/'prototype.tflite'
        target.write_bytes(converter.convert())
        static = static_check(target, Path(__file__).parents[1]/'firmware/main/wake_model.cpp', 524288)
        report = {'ordered_steps': steps, 'parameters': model.count_params(),
            'parity': parity, 'static': static, 'trained': False,
            'calibration': 'synthetic numeric fixtures; NOT final model calibration',
            'hardware_measured': False, 'release_eligible': False}
        (folder/'report.json').write_text(json.dumps(report, indent=2)+'\n')
        reports.append(report)
        print(json.dumps({'steps': steps, 'parameters': model.count_params(),
                          'bytes': static['bytes'], 'status': 'prototype-only'}), flush=True)
    return reports


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--upstream', type=Path, required=True)
    p.add_argument('--prototype-output', type=Path, required=True)
    a = p.parse_args()
    prototype(a.upstream, a.prototype_output)
