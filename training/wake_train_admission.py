# SPDX-License-Identifier: Apache-2.0
"""Conservative TRAIN-only quarantine; no relabeling or DEV filtering."""
import numpy as np
from wake_train_human_review import BASE_METHOD, HUMAN_METHOD, validate as validate_human

SYNTHETIC_SOURCES = {'OpenAI-Realtime-synthetic', 'Qwen3-TTS-hi-piku-synthetic-local'}


def retained_indices(admission, metadata, total):
    if (admission.get('method') not in (BASE_METHOD, HUMAN_METHOD) or
            admission.get('household_used') is not False or
            admission.get('DEV_used') is not False or admission.get('TEST_opened') is not False or
            admission.get('labels_changed') is not False or len(metadata) > total):
        raise ValueError('Independent TRAIN-only admission evidence required')
    if admission['method'] == HUMAN_METHOD:
        validate_human(admission, metadata)
    expected = {r['sha256'] for r in metadata if r['source'] in SYNTHETIC_SOURCES}
    accepted, quarantined = set(admission['accepted_sha256']), set(admission['quarantined_sha256'])
    if accepted & quarantined or accepted | quarantined != expected or not accepted:
        raise ValueError('Admission must partition every original synthetic TRAIN recording')
    keep = np.ones(total, bool)
    for i, row in enumerate(metadata):
        if row['source'] in SYNTHETIC_SOURCES:
            keep[i] = row['sha256'] in accepted
    original = np.flatnonzero(keep[:len(metadata)])
    return np.flatnonzero(keep), [metadata[i] for i in original], {
        'original_synthetic_recordings': len(expected), 'accepted_recordings': len(accepted),
        'quarantined_recordings': len(quarantined),
        'excluded_original_and_augmented_examples': int((~keep).sum()),
        'retained_examples': int(keep.sum()), 'all_descendants_follow_original': True,
        'no_confirmed_error_claim_from_ASR_alone': True}


def subset_phrase_events(archive, original_metadata, keep):
    if (len(archive['records']) != len(original_metadata) or
            any(a['sha256'] != b['sha256'] for a, b in zip(archive['records'], original_metadata))):
        raise ValueError('Phrase event ordering differs from original TRAIN metadata')
    original = [int(i) for i in keep if i < len(original_metadata)]
    return {'proof': {**archive['proof'], 'retained_original_TRAIN_indices': original},
            'records': [archive['records'][i] for i in original]}
