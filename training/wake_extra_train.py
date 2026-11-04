# SPDX-License-Identifier: Apache-2.0
"""Append consensus-audited synthetic TRAIN without rebuilding or moving DEV."""
import hashlib
import json
from pathlib import Path

import numpy as np
from hi_pikoo_review import content_match, normalized, validate
from hi_pikoo_train import read_audio, example
from wake_catalog_train import load_context, validate_catalog_row
from wake_natural_train import load_context as load_natural_context, validate_natural_row


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def natural_example(pcm, row, rng, repeat):
    """New natural originals keep their pitch; tempo is handled by wake_tempo.

    Legacy example(augment=True) includes resampling. Do not use it for these
    newly reviewed natural utterances. Keep the event clock on clean audio.
    """
    clean = np.asarray(pcm, np.float32).copy()
    if repeat == 0:
        return example(clean, row, rng, augment=False)
    from acoustic_augment import augment as room
    acoustic = room(clean, rng)
    return example(acoustic, row, rng, augment=False, timing_reference=clean)


def complete_base_metadata(x, y, w, metadata, events, groups):
    if (len(groups) != len(x) or len(metadata) != len(events['records']) or
            any(a['sha256'] != b['sha256'] for a, b in zip(metadata, events['records']))):
        raise ValueError('Original retained TRAIN metadata order differs')
    full_meta, full_events = list(metadata), list(events['records'])
    for i in range(len(metadata), len(x)):
        if y[i].max() > .5 or groups[i] not in {
                'ChildMandarin', 'LibriSpeech-train.100', 'ESC-50', 'public-speech-playlist'}:
            raise ValueError('Only audited public ordinary negatives can lack original phrase timing')
        n = int(np.flatnonzero(w[i] > 0)[-1])+1
        # This is explicitly a FEATURE digest, not an invented source-audio ID.
        item = {'sha256': hashlib.sha256(x[i].tobytes()).hexdigest(),
            'sha256_domain': 'prepared-TRAIN-feature-example', 'original_feature_index': i,
            'label': 0, 'source': groups[i], 'cohort': 'ordinary:public:ordinary',
            'contrast_class': 0, 'valid_steps': n, 'times_ms': [], 'completion_ms': 0}
        full_meta.append(item); full_events.append(item)
    return full_meta, {**events, 'records': full_events}


def append(x, y, w, metadata, events, groups, manifest, review_path,
           original_manifest, original_manifest_sha256, protected_path, output):
    if sha(original_manifest) != original_manifest_sha256:
        raise ValueError('Extra TRAIN source review belongs to another baseline')
    originals = json.loads(original_manifest.read_text())
    source_train = {r['speaker'] for r in originals if r['split'] == 'train'}
    source_dev = {r['speaker'] for r in originals if r['split'] != 'train'}
    source_hashes = {r['sha256'] for r in originals}
    originals_by_hash = {r['sha256']: r for r in originals}
    rows = json.loads(manifest.read_text())
    review = json.loads(review_path.read_text())
    reviews = {r['source_sha256']: r for r in review['records']}
    catalog = load_context(review, review_path, original_manifest_sha256)
    natural = load_natural_context(review, review_path, original_manifest_sha256)
    protected = set(json.loads(protected_path.read_text())['audio_sha256'].values())
    if not 1 <= len(rows) <= 200 or len({r['sha256'] for r in rows}) != len(rows):
        raise ValueError('Bounded unique extra TRAIN originals required')
    paths = []
    for row in rows:
        path = validate(row, manifest.parent, protected)
        if row['sha256'] in source_hashes:
            raise ValueError('Extra TRAIN cannot reuse an original TRAIN/DEV waveform')
        if row.get('source') == 'Qwen3-TTS-hi-piku-synthetic-local':
            validate_natural_row(row, natural, source_dev)
            paths.append(path)
            continue
        if row.get('source') == 'Google-Gemini-TTS-prebuilt':
            validate_catalog_row(row, catalog, source_train, source_dev)
            paths.append(path)
            continue
        evidence = reviews.get(row['sha256'])
        voice_review = originals_by_hash.get(row.get('source_voice_review_recording_sha256'))
        if (row['split'] != 'train' or row['speaker'] not in source_train or row['speaker'] in source_dev or
                row['sha256'] in source_hashes or row.get('content_review') != 'passed' or
                row.get('pronunciation_review') != 'passed' or not row.get('admitted_to_training') or
                row.get('perceived_style') != 'adult' or row.get('synthetic_style') != 'adult' or
                row.get('perceived_style_review') != 'passed' or not evidence or
                row.get('source') != 'OpenAI-Realtime-synthetic' or not voice_review or
                voice_review['speaker'] != row['speaker'] or voice_review.get('perceived_style') != 'adult' or
                voice_review.get('perceived_style_review') != 'passed' or
                row.get('source_voice_review_manifest_sha256') != original_manifest_sha256 or
                row.get('dual_audit_sha256') != sha(review_path) or
                not content_match(row, evidence['cloud']) or not content_match(row, evidence['local']) or
                normalized(evidence['cloud']) != normalized(evidence['local']) or
                row.get('target_contract') != 'hi-piku-piko-v2'):
            raise ValueError('Independent same-target consensus and TRAIN-only source identity required')
        paths.append(path)
    full_metadata, full_events = complete_base_metadata(x, y, w, metadata, events, groups)
    extra, extra_groups = [], []
    for row, path in zip(rows, paths):
        pcm = read_audio(path)
        for repeat in range(12 if row['label'] else 6):
            seed = f'audited-extra-v1/{row["sha256"]}/{repeat}'.encode()
            rng = np.random.default_rng(int.from_bytes(hashlib.sha256(seed).digest()[:8], 'little'))
            if row['source'] == 'Qwen3-TTS-hi-piku-synthetic-local':
                a, b, c, meta = natural_example(pcm, row, rng, repeat)
            else:
                a, b, c, meta = example(pcm, row, rng, augment=repeat > 0)
            if (a.dtype != x.dtype or b.dtype != y.dtype or c.dtype != w.dtype or
                    a.shape != x.shape[1:] or b.shape != y.shape[1:] or c.shape != w.shape[1:]):
                raise ValueError('Extra TRAIN frontend/interface differs from retained data')
            extra.append((a, b, c))
            meta.update(source=row['source'], sha256_domain='original-source-audio', repeat=repeat,
                        extra_audited_TRAIN=True)
            full_events['records'].append(meta); full_metadata.append(meta)
            extra_groups.append('legacy-positive' if row['label'] else 'legacy-negative')
    count = len(extra)
    result = tuple(np.concatenate([base, np.asarray([e[i] for e in extra])])
                   for i, base in enumerate((x, y, w)))
    proof = {'manifest_sha256': sha(manifest), 'review_sha256': sha(review_path),
        'original_manifest_sha256': original_manifest_sha256, 'source_recordings': len(rows),
        'positive_sources': sum(bool(r['label']) for r in rows), 'negative_sources': sum(not r['label'] for r in rows),
        'base_retained_examples': len(x), 'appended_examples': count,
        'base_prefix_arrays_unchanged': True, 'DEV_changed': False, 'TEST_opened': False,
        'household_used': False, 'ASR_is_not_phonetic_gold': True,
        'per_record_human_audition': all(r.get('per_record_human_audition') is True for r in rows),
        'human_reviewed_originals': sum(r.get('per_record_human_audition') is True for r in rows),
        'source_identities_not_new_speakers': not any(r['source'] == 'Google-Gemini-TTS-prebuilt' for r in rows),
        'new_catalog_voice_ids': sorted({r['provider_voice_id'] for r in rows if r['source'] == 'Google-Gemini-TTS-prebuilt'}),
        'catalog_age_is_provider_metadata_not_human_age_review': True,
        'real_speaker_independence_proven': False}
    proof['natural_human_reviewed_originals'] = sum(
        r['source'] == 'Qwen3-TTS-hi-piku-synthetic-local' for r in rows)
    proof['natural_augmentation'] = 'same-length acoustic-only; clean timing; no interpolation or pitch shift; separate pitch-preserving tempo stage'
    full_events['proof'] = {**events['proof'], 'extra_audited_TRAIN': proof}
    (output/'extra-train-metadata.json').write_text(json.dumps(full_metadata)+'\n')
    (output/'extra-train-events.json').write_text(json.dumps(full_events)+'\n')
    proof['metadata_sha256'] = sha(output/'extra-train-metadata.json')
    proof['events_sha256'] = sha(output/'extra-train-events.json')
    return (*result, full_metadata, full_events, [*groups, *extra_groups], proof)
