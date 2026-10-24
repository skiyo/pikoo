"""TRAIN-only causal features with explicit completion times and padding masks.

Never infer completion from a model score. A positive must retain its complete
annotated waveform. Non-target prefixes remain other; only complete annotated
near-phrases may receive their contrast class. Validation/test audio is not
decoded by this module.
"""
import hashlib
from pathlib import Path
import numpy as np
from contrastive_readout import category


def training_rows(rows, root, protected):
    """Validate split metadata first; hash only the selected TRAIN waveforms."""
    root = Path(root)
    groups, hashes, selected = {}, {}, []
    for row in rows:
        if (row.get('evaluation_only') or row.get('frozen_holdout') or
                str(row.get('source', '')).startswith('private-')):
            raise ValueError('Protected recordings cannot enter causal preparation')
        split = row['split']
        if split not in {'train', 'validation', 'test'}:
            raise ValueError('Unknown data split')
        group = row.get('speaker', row.get('voice', row.get('group')))
        if not group:
            raise ValueError('A speaker/group is required before augmentation')
        if group in groups and groups[group] != split:
            raise ValueError('Speaker/group leaks across splits')
        groups[group] = split
        digest = row['sha256']
        if digest in protected:
            raise ValueError('Protected recording hash in preparation manifest')
        if digest in hashes and hashes[digest] != split:
            raise ValueError('Waveform leaks across splits')
        hashes[digest] = split
        if split == 'train':
            actual = hashlib.sha256((root / row['path']).read_bytes()).hexdigest()
            if actual != digest:
                raise ValueError('TRAIN waveform hash changed')
            selected.append(row)
    if not selected:
        raise ValueError('No authorized TRAIN rows')
    return selected


def timestamped_features(pcm):
    from pymicro_features import MicroFrontend
    frontend, features, ends = MicroFrontend(), [], []
    pcm = np.asarray(np.clip(pcm, -32768, 32767), '<i2')
    for offset in range(0, len(pcm)-159, 160):
        result = frontend.process_samples(pcm[offset:offset+160].tobytes())
        if result.features:
            features.append(result.features)
            ends.append(offset+160)
    return np.asarray(features, np.float32), np.asarray(ends, np.int64)


def frame_targets(ends, completion_sample, complete_class, frames=600):
    """Align to the last consumed feature; mask right-padding with weight zero."""
    if frames < 3 or frames % 3:
        raise ValueError('Feature frame budget must be a multiple of three')
    ends = np.asarray(ends, np.int64)
    if ends.ndim != 1 or np.any(np.diff(ends) <= 0):
        raise ValueError('Feature timestamps must increase strictly')
    if len(ends) > frames:
        raise ValueError('Crop features and timestamps together before labeling')
    if not 0 <= complete_class < 14 or completion_sample <= 0:
        raise ValueError('Invalid completion annotation')
    steps = len(ends)//3
    labels, weights = np.zeros(frames//3, np.int32), np.zeros(frames//3, np.float32)
    if steps:
        labels[:steps] = np.where(ends[2:steps*3:3] >= completion_sample, complete_class, 0)
        weights[:steps] = (frames//3)/steps
    return labels, weights


def example(pcm, row, rng, background=None, frames=600):
    """One cold/warm example. Synthetic augmentation only; no held-out input."""
    if row['split'] != 'train' or row.get('evaluation_only') or row.get('frozen_holdout'):
        raise ValueError('Only TRAIN examples may be augmented')
    if str(row.get('source', '')).startswith('private-'):
        raise ValueError('Private recordings cannot enter causal training')
    pcm = np.asarray(pcm, np.float32).copy()
    if row['label'] and 'wake_end_sample' in row:
        end = int(row['wake_end_sample'])
        if not 0 < end <= len(pcm):
            raise ValueError('Invalid annotated complete wake end')
        pcm = pcm[:end]
    complete_class = category(row)
    # Long ordinary speech can be sampled at any point; its label remains other.
    max_speech = 56000 if row['label'] else 64000
    full_phrase = True
    if len(pcm) > max_speech:
        if row['label']:
            raise ValueError('Complete annotated phrase exceeds causal TRAIN budget')
        start = int(rng.integers(0, len(pcm)-max_speech+1))
        pcm = pcm[start:start+max_speech]
        # A truncated near-phrase is still a non-target, but cannot claim the
        # complete annotated contrast class. No source/failed clip is removed.
        complete_class, full_phrase = 0, False
    factor = float(rng.uniform(.9, 1.1))
    pcm = np.interp(np.arange(0, len(pcm), factor), np.arange(len(pcm)), pcm)
    if rng.random() < .25:
        from acoustic_augment import augment
        pcm = augment(pcm, rng)
    else:
        pcm *= rng.uniform(.35, 1.2)
    lead = int(rng.uniform(.3, 1.2)*16000)
    # >=240 ms leaves at least five complete three-feature steps after the
    # full waveform, accounting for frontend startup/step alignment.
    tail = int(rng.uniform(.24, .6 if row['label'] else 1.2)*16000)
    padded = np.pad(pcm, (lead, tail))
    padded += rng.normal(0, rng.uniform(0, 40), len(padded))
    if background is not None:
        full = background.apply(padded, lead)
        completion = len(full)-tail
    else:
        full, completion = padded, lead+len(pcm)
    features, ends = timestamped_features(full)
    # Drop a complete number of inference steps, preserving stride phase.
    drop = max(0, int(np.ceil((len(features)-frames)/3))*3)
    features, ends = features[drop:], ends[drop:]
    if complete_class and (not len(ends) or completion > ends[-1]-5*480):
        raise ValueError('Insufficient complete-word TRAIN supervision')
    labels, weights = frame_targets(ends, completion, complete_class, frames)
    valid = len(features)//3*3
    result = np.zeros((frames, 40), np.float32)
    result[:valid] = features[:valid]
    return result, labels, weights, {
        'warm': background is not None, 'valid_steps': valid//3,
        'completion_sample': int(completion), 'dropped_feature_frames': drop,
        'complete_class': int(complete_class), 'full_phrase_retained': full_phrase,
    }
