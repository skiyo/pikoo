#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Predeclare and validate a mixed-source TEST without synthesis or inference.

Real family recordings are TEST-only. Actual content labels must precede model
scores; intended prompts cannot supply vowel/age gold. No partial cohort pass.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
COHORTS = sorted(f'{age}:{accent}:{vowel}' for age, accent in
    [('adult', 'standard'), ('adult', 'Chinese-accent'), ('childlike', 'Chinese-accent')]
    for vowel in ('piku', 'piko'))
NEGATIVES = ('hi-alone', 'name-alone', 'Tikoo', 'nihao-Pikoo', 'ordinary-English', 'ordinary-Chinese')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protection_snapshot(registries, manifests):
    """Union metadata only, including TRAIN/DEV, consumed TEST and auditions."""
    hashes, sources = {}, {}
    for path in registries:
        value = json.loads(path.read_text())
        for key, digest in value['audio_sha256'].items():
            hashes[f'{sha(path)}/{key}'] = digest
        sources[str(path.resolve())] = sha(path)
    for path in manifests:
        rows = json.loads(path.read_text())
        if not isinstance(rows, list):
            raise ValueError('Original recording metadata manifests required')
        for index, row in enumerate(rows):
            hashes[f'{sha(path)}/{index}'] = row['sha256']
        sources[str(path.resolve())] = sha(path)
    if not hashes or any(not isinstance(x, str) or len(x) != 64 or
                         any(c not in '0123456789abcdef' for c in x) for x in hashes.values()):
        raise ValueError('Complete SHA256 recording protection required')
    return {'scope': 'All declared prior source metadata, no audio read',
            'audio_sha256': hashes, 'source_metadata_sha256': sources, 'metadata_only': True}


def timestamp(value):
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        raise ValueError('Timezone-aware evidence timestamps required')
    return stamp


def protocol(policy, policy_sha256, protected_sha256, declared_at):
    """Fixed 150 slots; the four pseudonyms do not mean previously unseen people."""
    if (policy.get('target') != 'hi-piku-piko-v2' or
            policy.get('development_passed') is not True or
            not policy.get('source_native_freeze_sha256') or not policy.get('micro_proof_sha256') or
            policy.get('required_test_cohorts') != COHORTS or
            len(policy.get('required_fresh_test_speakers', [])) != 2 or
            timestamp(declared_at) <= timestamp(policy['candidate_frozen_at'])):
        raise ValueError('Full native-qualified dual-target freeze required')
    slots = []
    voices = policy['required_fresh_test_speakers']
    for cohort in COHORTS:
        age, accent, vowel = cohort.split(':')
        synthetic = accent == 'standard'
        speakers = voices if synthetic else [f'family-{age}-{i}' for i in (1, 2)]
        for speaker in speakers:
            for _ in range(10):
                slots.append({'id': f'TEST-{len(slots)+1:03}', 'expected_label': 1,
                    'intended_cohort': cohort, 'speaker': speaker,
                    'source_kind': 'synthetic' if synthetic else 'family',
                    'role': 'child' if age == 'childlike' else 'adult',
                    'accent': accent, 'prompt': 'Hi ' + vowel})
    for category in NEGATIVES:
        for i in range(5):
            slots.append({'id': f'TEST-{len(slots)+1:03}', 'expected_label': 0,
                'negative_category': category, 'speaker': voices[i % 2],
                'source_kind': 'synthetic', 'role': 'adult', 'accent': 'standard'})
    return {'schema_version': 1, 'scope': 'post-freeze-mixed-independent-TEST-v1',
        'target': policy['target'], 'model_sha256': policy['model_sha256'],
        'policy_sha256': policy_sha256, 'protected_registry_sha256': protected_sha256,
        'candidate_frozen_at': policy['candidate_frozen_at'], 'declared_at': declared_at,
        'fixed_policy': {k: policy[k] for k in ('rolling', 'threshold')},
        'required_test_cohorts': COHORTS, 'minimum_targets_per_actual_cohort': 20,
        'slots': slots, 'family_recordings_TEST_only': True,
        'same_family_people_may_have_prior_tests': True,
        'protocol_does_not_authorize_recording': True,
        'family_two_sessions_and_eight_hour_acceptance_are_separate': True,
        'source_auditions_are_not_benchmark_cases': True}


def inside(root, value):
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Private TEST evidence path escapes bundle')
    return path


def family_proof(root, row, slot, plan, pcm, protocol_sha256):
    """Replay bounded transport proof; no trust in a success flag alone."""
    path = inside(root, row['capture_metadata_path'])
    capture = json.loads(path.read_text())
    if (capture.get('status') != 'captured-unlabelled-not-scored' or
            capture.get('test_slot_id') != row['id'] or
            capture.get('protocol_sha256') != protocol_sha256 or
            capture.get('speaker_id') != slot['speaker'] or
            capture.get('speaker_role_user_declared') != slot['role'] or
            capture.get('prompt') != slot['prompt'] or
            capture.get('model_sha256') != plan['model_sha256'] or
            capture.get('policy_sha256') != plan['policy_sha256'] or
            capture.get('split') != 'test' or capture.get('evaluation_only') is not True or
            capture.get('frozen_holdout') is not True or capture.get('synthetic') is not False or
            capture.get('real_child') != (slot['role'] == 'child') or
            capture.get('family_inputs_used') is not True or
            capture.get('training_or_tuning_allowed') is not False or
            capture.get('model_scored') is not False or
            capture.get('actual_content_label') is not None or
            timestamp(capture['started_at']) <= timestamp(plan['declared_at']) or
            row.get('created_at') != capture.get('completed_at') or
            timestamp(capture['completed_at']) < timestamp(capture['started_at'])):
        raise ValueError('New local family TEST capture evidence mismatch')
    sys.path.insert(0, str(ROOT / 'tools'))
    from wake_test_capture import decode_capture
    raw = inside(root, str(Path(row['capture_metadata_path']).parent / 'capture.log')).read_bytes()
    original, proof = decode_capture(raw)
    saved = capture['transport']
    if (original != pcm or any(saved.get(k) != v for k, v in proof.items()) or
            saved.get('old_model_scores_ignored') is not True):
        raise ValueError('Family PCM/transport evidence changed')


def validate_bundle(plan, rows, review, root, policy, policy_sha256, protected, protected_sha256,
                    manifest_sha256, protocol_sha256, repair_path=None, policy_path=None):
    """Validate all cases and human labels BEFORE opening the inference backend."""
    expected = protocol(policy, policy_sha256, protected_sha256, plan['declared_at'])
    if plan != expected:
        raise ValueError('Predeclared slots, policy or protected registry changed')
    slots = {slot['id']: slot for slot in plan['slots']}
    if len(rows) != len(slots) or {row['id'] for row in rows} != set(slots):
        raise ValueError('Complete fixed TEST required; missing/duplicate attempts cannot disappear')
    amended = {row['id'] for row in rows if row.get('source_repair_plan_sha256')}
    if repair_path:
        from wake_mixed_test_repair import repaired_rows
        from wake_mixed_test_labels import assemble
        replacements = repaired_rows(plan, root, policy_path, repair_path)
        original_rows = {row['id']: row for row in assemble(plan, root)}
        if (amended != set(replacements) or review.get('source_repair_plan_sha256') != sha(repair_path) or
                any(row != replacements.get(row['id'], original_rows[row['id']]) for row in rows)):
            raise ValueError('Explicit source repair evidence and exact new original rows required')
    elif amended or review.get('source_repair_plan_sha256'):
        raise ValueError('Repaired sources require the explicit pre-score amendment')
    if (review.get('protocol_sha256') != protocol_sha256 or
            review.get('manifest_sha256') != manifest_sha256 or
            review.get('model_sha256') != plan['model_sha256'] or
            review.get('policy_sha256') != plan['policy_sha256'] or
            review.get('labels_committed_before_model_scores') is not True or
            review.get('model_scored') is not False or
            review.get('reviewed_by') != 'human-content-only' or
            timestamp(review['reviewed_at']) <= timestamp(plan['declared_at'])):
        raise ValueError('Candidate-bound human content review required before model scoring')
    labels = review['records']
    if len(labels) != len(rows) or {r['id'] for r in labels} != set(slots):
        raise ValueError('Every attempt needs a blind content label')
    labels = {r['id']: r for r in labels}
    hashes, pcm_hashes, groups, categories, verified = set(), set(), Counter(), Counter(), []
    for row in rows:
        slot, label = slots[row['id']], labels[row['id']]
        if (row.get('status') != 'recorded' or row.get('split') != 'test' or
                row.get('evaluation_only') is not True or row.get('frozen_holdout') is not True or
                row.get('training_or_tuning_allowed') is not False or
                row.get('model_scored') is not False or row.get('cloud_uploaded') is not False or
                row.get('parent_sha256') or row.get('ancestry_parents') or
                row.get('source_audition') is not False or row.get('speaker') != slot['speaker'] or
                row.get('source_kind') != slot['source_kind'] or
                row.get('frozen_model_sha256') != plan['model_sha256'] or
                timestamp(row['created_at']) <= timestamp(plan['declared_at']) or
                timestamp(row['created_at']) > timestamp(review['reviewed_at'])):
            raise ValueError('Only fresh original TEST recordings for predeclared sources allowed')
        path = inside(root, row['path'])
        digest = sha(path)
        if digest != row['sha256'] or digest in protected or digest in hashes:
            raise ValueError('Changed, old/protected or duplicate TEST waveform')
        hashes.add(digest)
        with wave.open(str(path)) as audio:
            if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getframerate() not in (16000, 24000):
                raise ValueError('Original mono16 PCM at16/24kHz required')
            rate, count = audio.getframerate(), audio.getnframes()
            pcm = audio.readframes(count)
        pcm_digest = hashlib.sha256(pcm).hexdigest()
        if len(pcm) != count * 2 or not 0 < count / rate <= 10 or pcm_digest in pcm_hashes:
            raise ValueError('Truncated, overlong or duplicate PCM even with different WAV headers')
        pcm_hashes.add(pcm_digest)
        if slot['source_kind'] == 'family':
            if rate != 16000 or count != 64000:
                raise ValueError('Full bounded family capture required; never trim/crop')
            family_proof(root, row, slot, plan, pcm, protocol_sha256)
        elif (row.get('synthetic') is not True or row.get('real_child') is not False or
              row.get('family_inputs_used') is not False or row.get('reference_audio_used') is not False):
            raise ValueError('Held-out synthetic originals cannot contain family/child reference audio')
        if (label.get('sha256') != digest or label.get('quality_valid') is not True or
                timestamp(label['reviewed_at']) < timestamp(row['created_at']) or
                timestamp(label['reviewed_at']) > timestamp(review['reviewed_at']) or
                type(label.get('actual_label')) is not int or label['actual_label'] != slot['expected_label'] or
                label.get('actual_age') != slot['role'] or label.get('actual_accent') != slot['accent'] or
                label.get('no_repetition_or_extra_words') is not True):
            raise ValueError('Do not replace missing content or child age with a requested prompt')
        group = None
        if slot['expected_label']:
            variant = label.get('actual_variant')
            end = label.get('completion_ms')
            if (variant not in ('piku', 'piko') or type(end) not in (int, float) or
                    not 0 < end <= count / rate * 1000 or label.get('complete_hi_and_name') is not True):
                raise ValueError('Actual complete target and pre-score endpoint labels required')
            age = 'childlike' if slot['role'] == 'child' else 'adult'
            group = f'{age}:{slot["accent"]}:{variant}'
            groups[group] += 1
        else:
            if (label.get('actual_variant') != 'non-target' or
                    label.get('negative_category') != slot['negative_category']):
                raise ValueError('Near-target negative content must be confirmed independently')
            categories[slot['negative_category']] += 1
        verified.append({'id': row['id'], 'path': path, 'label': slot['expected_label'],
            'cohort': group, 'completion_ms': label.get('completion_ms'),
            'source_kind': slot['source_kind'], 'role': slot['role'], 'sha256': digest})
    if dict(groups) != {group: 20 for group in COHORTS} or dict(categories) != {cat: 5 for cat in NEGATIVES}:
        raise ValueError('Actual six-cohort and negative coverage incomplete; no partial TEST pass')
    return verified
