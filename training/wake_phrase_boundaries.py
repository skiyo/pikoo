# SPDX-License-Identifier: Apache-2.0
"""Emphasize TRAIN-only incomplete prefixes and competitor speech endings.

No label, feature, threshold, DEV, TEST or household changes. The fixed factor
is applied before TRAIN cohort/event balancing. A complete target's positive
event keeps its original weight at this stage.
"""
import numpy as np


def emphasize(archive, labels, weights):
    proof, records = archive['proof'], archive['records']
    if (proof.get('every_original_TRAIN_array_byte_equal') is not True or
            proof.get('household_used') is not False or proof.get('DEV_waveforms_read') is not False or
            proof.get('TEST_opened') is not False or proof.get('source_manifest_labels_unchanged') is not True or
            len(records) > len(labels) or labels.shape != weights.shape):
        raise ValueError('Verified original TRAIN event timing required')
    result = np.array(weights, copy=True)
    counts = {'complete_target_prefix_steps': 0, 'competitor_ending_steps': 0}
    for i, row in enumerate(records):
        if (bool(row['label']) != bool(labels[i].max() > .5) or
                bool(row['label']) != (row['contrast_class'] == 1)):
            raise ValueError('TRAIN boundary metadata disagrees with original labels')
        if row['contrast_class'] == 0:
            continue
        n = row['valid_steps']
        times = np.asarray(row['times_ms'])
        if len(times) != n or n > labels.shape[1] or not np.isfinite(times).all():
            raise ValueError('Malformed original TRAIN event clock')
        end = row['completion_ms']
        if not np.isfinite(end):
            raise ValueError('Nonfinite TRAIN completion time')
        if row['label']:
            event = (times >= end-600) & (times < end-120)
            key = 'complete_target_prefix_steps'
        elif row['contrast_class'] in (2, 3, 4, 5):
            event = (times >= end-120) & (times <= end+450)
            key = 'competitor_ending_steps'
        else:
            raise ValueError('Unknown TRAIN phrase family')
        event &= weights[i, :n] > 0
        if np.any(labels[i, :n][event] > .5):
            raise ValueError('A hard-negative boundary overlaps a complete positive event')
        result[i, :n][event] *= 4
        counts[key] += int(event.sum())
    if any(n == 0 for n in counts.values()):
        raise ValueError('Both positive prefixes and competitor endings required')
    return result, {'factor': 4, **counts,
        'target_prefix_ms_relative_to_completion': [-600, -120],
        'competitor_ending_ms_relative_to_completion': [-120, 450],
        'scope': 'original verified TRAIN metadata only, before event/cohort balancing',
        'labels_changed': False, 'positive_events_amplified_here': False,
        'trigger_policy_changed': False}
