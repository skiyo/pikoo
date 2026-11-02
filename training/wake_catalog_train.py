# SPDX-License-Identifier: Apache-2.0
"""Explicit human-reviewed catalog originals, never prompt-only admission.

Provider catalog age is metadata, not a human perceived-age annotation or
biometric speaker-independence proof. This path admits adult TRAIN targets only;
DEV content-review clips and unreviewed descendants cannot enter through it.
"""
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_context(review, review_path, original_manifest_sha256):
    declaration = review.get('human_catalog_admission')
    if declaration is None:
        return None
    evidence = {}
    for name in ('source_isolation', 'human_feedback'):
        path = (review_path.parent/declaration[name+'_file']).resolve()
        if not path.is_relative_to(review_path.parent.resolve()) or sha(path) != declaration[name+'_sha256']:
            raise ValueError('Catalog admission evidence path/hash differs')
        evidence[name] = json.loads(path.read_text())
    isolation, feedback = evidence['source_isolation'], evidence['human_feedback']
    if (isolation.get('used_voice_ID_collision') is not False or
            original_manifest_sha256 not in isolation['source_manifests_sha256'].values() or
            feedback.get('household_recordings_used') is not False or
            feedback.get('TEST_opened') is not False or
            feedback.get('wake_scores_used_for_selection') is not False):
        raise ValueError('TRAIN source isolation and independent human feedback required')
    for path, digest in isolation['source_manifests_sha256'].items():
        if sha(Path(path)) != digest:
            raise ValueError('Historical source identity manifest changed')
    return {'declaration': declaration,
            'voices': {v['id']: v for v in isolation['selected']},
            'feedback': {r['source_sha256']: r for r in feedback['records']}}


def validate_catalog_row(row, context, source_train, source_dev):
    if context is None:
        raise ValueError('Explicit catalog source and human review evidence required')
    feedback = context['feedback'].get(row['sha256'], {})
    voice = context['voices'].get(row.get('provider_voice_id'), {})
    if (row.get('source') != 'Google-Gemini-TTS-prebuilt' or
            row['split'] != 'train' or row['speaker'] in source_train | source_dev or
            row['speaker'] != 'google-prebuilt:'+row.get('provider_voice_id', '') or
            voice.get('type') != 'prebuilt' or voice.get('language_code') != 'en-US' or
            not voice.get('description') or row.get('label') != 1 or
            row.get('synthetic_style') != 'adult' or row.get('accent') != 'standard' or
            row.get('perceived_style_review') != 'provider-catalog-adult-only' or
            row.get('per_record_human_audition') is not True or
            row.get('human_review_sha256') != context['declaration']['human_feedback_sha256'] or
            row.get('source_isolation_sha256') != context['declaration']['source_isolation_sha256'] or
            feedback.get('accepted') is not True or 'original_DEV_index' in feedback or
            feedback.get('source_id') != row.get('id') or
            feedback.get('heard_variant') not in {'piku', 'piko'} or
            row.get('pronunciation_variant') != feedback.get('heard_variant') or
            row.get('target_contract') != 'hi-piku-piko-v2' or
            row.get('content_review') != 'passed' or row.get('pronunciation_review') != 'passed' or
            row.get('admitted_to_training') is not True):
        raise ValueError('Catalog TRAIN original lacks matching full-utterance human approval')
