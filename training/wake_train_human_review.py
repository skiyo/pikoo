# SPDX-License-Identifier: Apache-2.0
"""Versioned human content overrides for quarantined synthetic TRAIN targets.

No corpus I/O, audio upload, model selection or implicit pronunciation relabeling.
The caller must verify the review pack and original waveform hashes first.
"""
import copy

BASE_METHOD = 'complete-independent-blind-ASR-content-agreement'
HUMAN_METHOD = 'independent-ASR-partition-with-explicit-human-TRAIN-content-overrides'


def merge(base, feedback):
    if (base.get('method') != BASE_METHOD or
            feedback.get('scope') != 'independent-human-content-review-of-quarantined-synthetic-TRAIN-originals' or
            feedback.get('original_manifest_sha256') != base.get('original_manifest_sha256') or
            feedback.get('per_record_human_listening') is not True or
            any(feedback.get(k) is not False for k in
                ('household_used', 'DEV_used', 'TEST_opened', 'selection_used_wake_scores', 'labels_changed')) or
            any(base.get(k) is not False for k in ('household_used', 'DEV_used', 'TEST_opened', 'labels_changed'))):
        raise ValueError('Independent original TRAIN human review with unchanged labels required')
    accepted, quarantined = set(base['accepted_sha256']), set(base['quarantined_sha256'])
    if accepted & quarantined:
        raise ValueError('Original ASR partition overlaps')
    seen, promoted = set(), set()
    for row in feedback['records']:
        digest = row['source_sha256']
        if (digest in seen or digest not in quarantined or row.get('original_split') != 'train' or
                row.get('original_label') != 1):
            raise ValueError('Review must bind to distinct quarantined original TRAIN positives')
        seen.add(digest)
        if row.get('accepted') is True:
            if row.get('complete_target_phrase') is not True or row.get('accepted_names') != ['piku', 'piko']:
                raise ValueError('Explicit complete target-phrase confirmation required')
            promoted.add(digest)
        elif row.get('accepted') not in (False, None):
            raise ValueError('Unknown review verdict')
    if not promoted:
        raise ValueError('No human-confirmed target original to restore')
    result = copy.deepcopy(base)
    result.pop('group_counts', None)  # Original counts remain in base_ASR_admission.
    result.update(method=HUMAN_METHOD, accepted_sha256=sorted(accepted | promoted),
                  quarantined_sha256=sorted(quarantined-promoted),
                  base_ASR_admission=copy.deepcopy(base), human_override_review=copy.deepcopy(feedback),
                  human_restored_recordings=sorted(promoted),
                  all_restored_augmented_descendants_follow_original=True,
                  ASR_is_not_phonetic_ground_truth=True,
                  specific_vowels_not_inferred_from_full_target_acceptance=True)
    result['quarantine_note'] = 'Only explicitly human-confirmed originals are restored; all unconfirmed sources and descendants stay quarantined.'
    return result


def validate(admission, metadata):
    expected = merge(admission['base_ASR_admission'], admission['human_override_review'])
    for key in ('method', 'original_manifest_sha256', 'accepted_sha256', 'quarantined_sha256',
                'human_restored_recordings'):
        if admission[key] != expected[key]:
            raise ValueError('Human TRAIN admission differs from original partition and explicit verdicts')
    restored = set(expected['human_restored_recordings'])
    matches = [r for r in metadata if r['sha256'] in restored]
    if {r['sha256'] for r in matches} != restored or any(r['label'] != 1 for r in matches):
        raise ValueError('Restored source must match the original positive feature metadata')
