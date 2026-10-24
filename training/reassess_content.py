"""Versioned TRAIN-only correction of a known transcript-comparison defect.

This does not transcribe again, alter audio/labels, or adjudicate ambiguous
speech. The local pi-ke negative policy already accepts these spellings; the
older Google comparator used literal spelling instead. Raw records remain
embedded unchanged in the derived observation. Other rejection flags survive.
"""
import copy
import hashlib
import json

from review_google_corpus import content_matches, normalize
from review_local_corpus import content_approved

RULE = 'train-negative-pi-ke-comparator-reassessment-v1'
OLD_RULE = 'exact-transcript-with-target-homophones-v3-no-extra-Latin'


def reassess(row, record):
    if (row.get('split') != 'train' or row.get('label') != 0
            or row.get('source') not in {'Google-Gemini-TTS-synthetic',
                                         'Qwen3-TTS-synthetic-local'}
            or not row.get('synthetic') or row.get('real_child')
            or row.get('family_inputs_used') or row.get('reference_audio_used')
            or row.get('evaluation_only') or row.get('frozen_holdout')):
        raise ValueError('Reassessment requires eligible fictional TRAIN negatives')
    if (row['sha256'] != record.get('sha256') or record.get('label') != 0
            or record.get('rule') != OLD_RULE
            or record.get('diagnostic_only') is not False
            or record.get('admission_eligible') is not True
            or not isinstance(record.get('transcript'), str)
            or not str(record.get('model', '')).startswith('gemini-')):
        raise ValueError('Requires an unchanged independent Google observation')
    heard = record['transcript']
    if (record.get('approved') is not False
            or any(record.get(k) is False for k in ['local_approved', 'prior_approved'])
            or normalize(row.get('text', '')) != '你好皮克'
            or content_matches(row['text'], heard)
            or not content_approved(row, heard)):
        raise ValueError('Not the documented pi-ke orthographic comparison defect')
    raw = copy.deepcopy(record)
    result = copy.deepcopy(record)
    result.update(approved=True, rule=RULE, assessment_correction_only=True,
                  prior_raw_observation=raw,
                  prior_raw_observation_sha256=hashlib.sha256(json.dumps(
                      raw, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
                  limitations='Content only; no tone, model, child or hardware acceptance')
    return result
