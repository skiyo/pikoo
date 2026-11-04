# SPDX-License-Identifier: Apache-2.0
"""Admit explicitly reviewed fictional TRAIN originals, never source auditions.

This validates evidence, not voice age or phonetics. Prompt age and ASR agreement
cannot replace a human verdict on the exact waveform. No audio/model/API I/O.
"""
import hashlib
import json


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_context(review, review_path, original_manifest_sha256):
    declaration = review.get('human_natural_admission')
    if declaration is None:
        return None
    if declaration.get('original_manifest_sha256') != original_manifest_sha256:
        raise ValueError('Natural TRAIN evidence belongs to another baseline')
    files = {}
    names = ['raw_manifest', 'human_feedback', 'source_reservation', 'never_train']
    if 'matched_pairs_file' in declaration:
        names.append('matched_pairs')
    for name in names:
        path = (review_path.parent/declaration[name+'_file']).resolve()
        if (not path.is_relative_to(review_path.parent.resolve()) or
                sha(path) != declaration[name+'_sha256']):
            raise ValueError('Natural TRAIN evidence path/hash differs')
        files[name] = json.loads(path.read_text())
    feedback, reservation = files['human_feedback'], files['source_reservation']
    if (feedback.get('scope') != 'per-record-human-synthetic-TRAIN-content-and-style' or
            feedback.get('per_record_human_listening') is not True or
            any(feedback.get(k) is not False for k in
                ('household_used', 'DEV_used', 'TEST_opened', 'wake_scores_used_for_selection', 'labels_changed')) or
            reservation.get('source_SPLIT') != 'TRAIN-only reserved before generation; neverfutureTEST' or
            reservation.get('household_used') is not False or reservation.get('TEST_opened') is not False):
        raise ValueError('Explicit TRAIN-only human content/style review required')
    originals, verdicts = files['raw_manifest'], feedback['rows']
    if (len({r['sha256'] for r in originals}) != len(originals) or
            len({r['source_sha256'] for r in verdicts}) != len(verdicts)):
        raise ValueError('Duplicate original or human verdict')
    original_by_hash = {r['sha256']: r for r in originals}
    pairs = {}
    if reservation.get('matched_pair_review_required') is True and 'matched_pairs' not in files:
        raise ValueError('Matched TRAIN reservation requires hashed pair evidence')
    if 'matched_pairs' in files:
        for pair in files['matched_pairs']:
            positive, negative = pair['positive_sha256'], pair['negative_sha256']
            p, n = original_by_hash.get(positive, {}), original_by_hash.get(negative, {})
            if (positive == negative or positive in pairs or negative in pairs or
                    not p or not n or type(p.get('label')) is not int or p['label'] != 1 or
                    type(n.get('label')) is not int or n['label'] != 0 or
                    p.get('speaker') != n.get('speaker')):
                raise ValueError('Matched TRAIN pairs need unique same-family P/T originals')
            pairs[positive], pairs[negative] = negative, positive
        if set(pairs) != set(original_by_hash):
            raise ValueError('Matched TRAIN pairs must cover every raw original exactly once')
    return {'declaration': declaration, 'originals': {r['sha256']: r for r in originals},
            'feedback': {r['source_sha256']: r for r in verdicts},
            'sources': set(reservation['source_families']),
            'never_train': set(files['never_train']['audio_sha256'].values()),
            'matched_pairs': pairs}


def validate_natural_row(row, context, source_dev):
    if context is None:
        raise ValueError('Natural TRAIN source and human evidence required')
    digest = row['sha256']
    partner_digest = context.get('matched_pairs', {}).get(digest)
    if partner_digest:
        partner = context['originals'][partner_digest]
        verdict = context['feedback'].get(partner_digest, {})
        if (partner_digest in context['never_train'] or
                verdict.get('approved_for_TRAIN') is not True or
                verdict.get('human_content_correct') is not True or
                verdict.get('human_actual_perceived_style') not in {'adult', 'childlike'} or
                verdict.get('original_binary_label') != partner['label'] or
                verdict.get('expected_text') != partner['text'] or
                verdict.get('source_family') != partner['speaker']):
            raise ValueError('Both matched TRAIN originals need explicit content/style approval')
    original = context['originals'].get(digest, {})
    feedback = context['feedback'].get(digest, {})
    identity = ('sha256', 'speaker', 'text', 'label', 'split', 'source', 'path')
    if (not original or any(row.get(k) != original.get(k) for k in identity) or
            digest in context['never_train'] or original.get('audition_only') is not False or
            original.get('purpose') != 'TRAIN-candidate-quarantine' or
            row.get('source') != 'Qwen3-TTS-hi-piku-synthetic-local' or
            row.get('split') != 'train' or row['speaker'] not in context['sources'] or
            row['speaker'] in source_dev or type(row.get('label')) is not int or row['label'] not in (0, 1) or
            any(original.get(k) is not False for k in
                ('real_child', 'reference_audio_used', 'family_inputs_used')) or
            any(original.get(k) for k in ('evaluation_only', 'frozen_holdout', 'parent_sha256', 'ancestry_parents')) or
            original.get('synthetic') is not True or
            feedback.get('approved_for_TRAIN') is not True or
            feedback.get('human_content_correct') is not True or
            feedback.get('original_binary_label') != row['label'] or
            feedback.get('expected_text') != row['text'] or
            feedback.get('source_family') != row['speaker'] or
            feedback.get('human_actual_perceived_style') not in {'adult', 'childlike'} or
            row.get('perceived_style') != feedback['human_actual_perceived_style'] or
            row.get('synthetic_style') != row.get('perceived_style') or
            row.get('perceived_style_review') != 'passed' or
            row.get('per_record_human_audition') is not True or
            row.get('human_review_sha256') != context['declaration']['human_feedback_sha256'] or
            row.get('raw_manifest_sha256') != context['declaration']['raw_manifest_sha256'] or
            row.get('target_contract') != 'hi-piku-piko-v2' or
            row.get('content_review') != 'passed' or row.get('pronunciation_review') != 'passed' or
            row.get('admitted_to_training') is not True):
        raise ValueError('Natural TRAIN original lacks matching explicit content/style approval')
