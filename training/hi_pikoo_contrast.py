# SPDX-License-Identifier: Apache-2.0
"""Phrase-family supervision; deploy only the full-wake probability.

No data/network/device access on import. Every non-wake family stays rejected;
families teach missing greeting/name/consonant distinctions during training.
"""
import numpy as np
from hi_pikoo_review import normalized

FAMILIES = ['ordinary', 'full_wake', 't_name', 'hi_only', 'name_only', 'missing_last_syllable']


def family(row):
    if row['label']:
        return 1
    text = normalized(row.get('text', ''))
    if text in {'hitikoo', 'hitiko'}:
        return 2
    if text == 'hi':
        return 3
    if text in {'pikoo', 'piko'}:
        return 4
    if text in {'hip', 'hipee'}:
        return 5
    return 0


def targets(info, steps=200):
    y, w = np.zeros((len(info), steps), np.int32), np.zeros((len(info), steps), np.float32)
    for i, meta in enumerate(info):
        n, c = meta['valid_steps'], meta['contrast_class']
        w[i, :n] = 1
        if c:
            times = np.asarray(meta['times_ms'])
            end = meta['completion_ms']
            event = (times >= end) & (times <= end+300)
            y[i, :n][event] = c
            w[i, :n][((times >= end-120) & (times < end)) |
                      ((times > end+300) & (times < end+600))] = 0
    return y, w


def balance(y, w):
    counts = np.bincount(y[w > 0], minlength=len(FAMILIES))
    if np.any(counts[1:] == 0):
        raise ValueError('All five phrase-event families must be represented in TRAIN')
    factors = np.clip(counts[1:].sum()/(5*counts[1:]), .25, 8.)
    result = w.copy()
    for c, factor in enumerate(factors, 1):
        result[y == c] *= 12*factor
    return result, {'event_steps': counts.tolist(), 'event_factors': factors.tolist()}


def build(upstream, ordered_steps, seed, channels=24, batch_normalization=False):
    import tensorflow as tf
    from hi_pikoo_model import build as binary
    base = binary(upstream, ordered_steps, seed, channels, batch_normalization)
    x = base.get_layer('wake_probability').input
    x = tf.keras.layers.Conv2D(len(FAMILIES), 1, name='phrase_family_logits')(x)
    x = tf.keras.layers.Softmax(axis=-1, name='phrase_family_probability')(x)
    return tf.keras.Model(base.input, tf.keras.layers.Reshape((-1, len(FAMILIES)))(x))


def wake_view(model):
    import tensorflow as tf
    return tf.keras.Model(model.input, model.output[:, :, 1])
