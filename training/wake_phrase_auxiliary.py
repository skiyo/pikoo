# SPDX-License-Identifier: Apache-2.0
"""Training-only phrase discrimination, preserving the binary deployment ABI."""
import numpy as np
from hi_pikoo_contrast import FAMILIES, targets, balance


def training_targets(archive, labels, weights):
    proof, records = archive['proof'], archive['records']
    if (proof.get('every_original_TRAIN_array_byte_equal') is not True or
            proof.get('household_used') is not False or
            proof.get('DEV_waveforms_read') is not False or
            proof.get('TEST_opened') is not False or
            proof.get('source_manifest_labels_unchanged') is not True or len(records) > len(labels)):
        raise ValueError('Byte-verified TRAIN-only phrase metadata required')
    for index, row in enumerate(records):
        if (bool(row['label']) != bool(labels[index].max() > .5) or
                bool(row['label']) != (row['contrast_class'] == 1)):
            raise ValueError('Phrase targets disagree with binary TRAIN labels')
    if np.any(labels[len(records):] > .5):
        raise ValueError('Unmapped positive TRAIN example')
    y = np.zeros(labels.shape, np.int32)
    w = (weights > 0).astype(np.float32)
    y[:len(records)], w[:len(records)] = targets(records, labels.shape[1])
    w, summary = balance(y, w)
    return y, w, {'families': FAMILIES, **summary,
                  'scope': 'TRAIN-only auxiliary labels; no deployment policy change'}


def attach(binary):
    import tensorflow as tf
    x = binary.get_layer('wake_probability').input
    x = tf.keras.layers.Conv2D(len(FAMILIES), 1, name='auxiliary_phrase_logits')(x)
    x = tf.keras.layers.Softmax(name='auxiliary_phrase_probability')(x)
    auxiliary = tf.keras.layers.Reshape((-1, len(FAMILIES)), name='auxiliary_phrase')(x)
    # The binary submodel retains its sigmoid and scalar [1,3,40] streaming
    # output. Auxiliary layers are not traversed or exported by stream(binary).
    return tf.keras.Model(binary.input, {'wake': binary.output, 'phrase': auxiliary})
