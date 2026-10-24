"""Audit-only correction for predeclared TRAIN phonetic input spellings.

No ASR call, audio/label edit or automatic corpus admission occurs here. This
handles a specific metadata comparator defect: the source text is romanized
while the already declared spoken transcript is Chinese. Keep the returned
observation alongside the unchanged raw observation in versioned evidence.
"""
import copy
import hashlib
import json
import re

from review_google_corpus import content_matches
from review_local_corpus import content_approved
from corpus_ancestry import parents

RULE = 'train-english-phonetic-surface-comparator-reassessment-v1'
OLD_RULE = 'exact-transcript-with-target-homophones-v3-no-extra-Latin'


def _fingerprint(record):
    return hashlib.sha256(json.dumps(record, ensure_ascii=False,
                                    sort_keys=True).encode()).hexdigest()


def reassess(row, record, local_records, protected_hashes):
    """Return derived content evidence; caller still verifies waveform hashes."""
    digest = row.get('sha256', '')
    if (not re.fullmatch('[0-9a-f]{64}', digest) or digest in protected_hashes
            or row.get('split') != 'train' or row.get('label') != 1
            or row.get('source') != 'Qwen3-TTS-synthetic-local'
            or row.get('synthetic') is not True
            or any(row.get(k) is not False for k in
                   ['real_child', 'family_inputs_used', 'reference_audio_used'])
            or any(row.get(k) for k in ['evaluation_only', 'frozen_holdout'])
            or parents(row) or row.get('english_phonetic_surface') is not True
            or row.get('text') not in {'Ni hao, pee coo.', 'Ni hao! Pee koo!'}
            or row.get('expected_spoken_transcript') != '你好皮酷'):
        raise ValueError('Requires unprotected raw fictional TRAIN phonetic metadata')
    if (record.get('sha256') != digest or record.get('label') != 1
            or record.get('rule') != OLD_RULE
            or record.get('diagnostic_only') is not False
            or record.get('admission_eligible') is not True
            or record.get('approved') is not False
            or any(record.get(k) is False for k in ['local_approved', 'prior_approved'])
            or not str(record.get('model', '')).startswith('gemini-')
            or not isinstance(record.get('transcript'), str)):
        raise ValueError('Requires unchanged independent Google comparator failure')
    heard = record['transcript']
    if (content_matches(row['text'], heard)
            or not content_matches(row['expected_spoken_transcript'], heard)):
        raise ValueError('Not the predeclared phonetic-surface comparison defect')
    if not local_records:
        raise ValueError('Requires existing agreeing local observations')
    for local in local_records:
        if (local.get('sha256') != digest or local.get('label') != 1
                or not str(local.get('model', '')).startswith('qwen3-asr-')
                or local.get('approved') is not True
                or any(local.get(k) is False for k in ['local_approved', 'prior_approved'])
                or not isinstance(local.get('transcript'), str)
                or not content_approved(row, local['transcript'])):
            raise ValueError('Local disagreement or identity mismatch remains quarantined')
    result = copy.deepcopy(record)
    result.update(approved=True, rule=RULE, assessment_correction_only=True,
                  prior_raw_observation=copy.deepcopy(record),
                  prior_raw_observation_sha256=_fingerprint(record),
                  corroborating_local_observations=copy.deepcopy(local_records),
                  corroborating_local_sha256=[_fingerprint(x) for x in local_records],
                  expected_spoken_transcript=row['expected_spoken_transcript'],
                  source_text=row['text'],
                  limitations='Content only; no tone, wake accuracy, child or hardware acceptance')
    return result
