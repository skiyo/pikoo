#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build a private corpus from source auditions and blind ASR evidence.

ASR/name agreement plus a reviewed source is a noisy synthetic-data admission
rule, not gold phoneme alignment or real-child evidence. Confusable piko
negatives remain quarantined without an explicit per-record vowel review.
"""
import argparse
import json
from pathlib import Path
import wave
from hi_pikoo_review import content_match, normalized, validate
from hi_pikoo_contract import relabel_for_contract, validate_contract


def decide(row, review, feedback):
    if (row.get('evaluation_only') or row.get('frozen_holdout') or
        row.get('family_inputs_used') or row.get('reference_audio_used') or
        row.get('real_child') or row['split'] not in {'train', 'validation'}):
        return None, 'protected-or-ineligible-source'
    if review is None:
        return None, 'blind-ASR-content-disagreement-or-missing'
    if not content_match(row, review['transcript']):
        return None, 'current-content-rule-disagreement'
    if row['label'] == 0 and normalized(row['text']) == 'hipiko':
        return None, 'piko-vowel-needs-explicit-per-record-review'
    if row['source'] == 'OpenAI-Realtime-synthetic':
        if row.get('recipe') not in {'literal-v2', 'literal-adult-v3', 'literal-adult-v4'}:
            return None, 'failed-annotated-recipe'
        if not row.get('transcript') or not content_match(row, row['transcript']):
            return None, 'generator-transcript-disagreement'
        if feedback.get('clips', {}).get('train-0060', {}).get('pronunciation_piku') != 'accepted':
            return None, 'adult-source-audition-missing'
        style, gender = 'adult', 'unspecified'
        source_evidence = 'fixed-voice adult synthesis; user A/B pronunciation audition'
    elif row['source'] == 'Qwen3-TTS-hi-piku-synthetic-local':
        sha = row.get('source_audition_sha256')
        if sha not in feedback.get('accepted_source_hashes', {}):
            return None, 'source-audition-not-accepted'
        source = feedback['accepted_source_hashes'][sha]
        if source.get('perceived_style') != 'childlike' or not source.get('pronunciation_piku_accepted'):
            return None, 'childlike-source-or-pronunciation-unaccepted'
        style, gender = 'childlike', source['perceived_gender']
        source_evidence = 'user audition of source design; not per-record age verification'
    else:
        return None, 'unapproved-generator'
    result = {**row, 'synthetic_style_requested': row.get('synthetic_style'),
        'synthetic_style': style, 'perceived_style': style,
        'perceived_gender': gender, 'perceived_style_review': 'passed',
        'perceived_style_evidence': source_evidence,
        'content_review': 'passed', 'pronunciation_review': 'passed',
        'pronunciation_evidence': 'source audition + blind exact-content ASR; not a phoneme oracle',
        'independent_asr_transcript': review['transcript'],
        'prior_content_screen_result': review.get('local_content_passed'),
        'admitted_to_training': True, 'real_child': False}
    if row['label']:
        manual = feedback.get('manual_vowel_reviews', {}).get(row['sha256'])
        result['pronunciation_variant'] = manual['heard_name_sound'] if manual else (
            'piko' if normalized(review['transcript']) == 'hipiko' else 'piku')
        result['variant_evidence'] = 'user per-record vowel audit' if manual else 'ASR inferred; not gold phoneme annotation'
    else:
        result['pronunciation_variant'] = 'non-target'
    return result, None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--manifest', type=Path, required=True, action='append')
    p.add_argument('--review', type=Path, required=True, action='append')
    p.add_argument('--source-feedback', type=Path, required=True)
    p.add_argument('--protected-hashes', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--target-contract', type=Path, required=True)
    a = p.parse_args()
    root = a.root.resolve()
    contract = validate_contract(json.loads(a.target_contract.read_text()))
    feedback = json.loads(a.source_feedback.read_text())
    protected = set(json.loads(a.protected_hashes.read_text())['audio_sha256'].values())
    reviews = {r['sha256']: r for f in a.review for r in json.loads(f.read_text())}
    admitted, quarantined, hashes = [], [], {}
    for manifest in a.manifest:
        for row in json.loads(manifest.read_text()):
            # TEST is never opened by this tool.
            if row['split'] == 'test':
                raise ValueError('Sealed TEST cannot enter admission or training')
            # Reject protected metadata/hashes before reading even WAV bytes.
            audio = validate(row, manifest.parent, protected)
            if not audio.is_relative_to(root):
                raise ValueError('Source path outside new synthetic root')
            actual = row['sha256']  # validate() already bound original bytes.
            if actual in hashes and hashes[actual] != (row['split'], row['label']):
                raise ValueError('Duplicate waveform has conflicting split/label')
            if actual in hashes:
                continue
            hashes[actual] = (row['split'], row['label'])
            revised = relabel_for_contract(row, contract['target'])
            accepted, reason = decide(revised, reviews.get(actual), feedback)
            with wave.open(str(audio)) as wav:
                seconds = wav.getnframes()/wav.getframerate()
            if accepted:
                from hi_pikoo_train import read_audio
                from hi_pikoo_timing import timing
                details = timing(read_audio(audio))
                accepted['source_timing'] = details
                seconds = details['view_ms']/1000
            if revised['label'] and not .3 <= seconds <= 3.5:
                accepted, reason = None, 'positive-active-view-too-long-or-short-no-word-repair'
            if accepted:
                admitted.append({**accepted, 'path': str(audio.relative_to(root))})
            else:
                quarantined.append({'id': row.get('id', row.get('profile')),
                    'sha256': actual, 'reason': reason})
    groups, wavs = {}, {}
    for row in admitted:
        if groups.setdefault(row['speaker'], row['split']) != row['split']:
            raise ValueError('Speaker/prompt family appears in both TRAIN and DEV')
        if wavs.setdefault(row['sha256'], row['split']) != row['split']:
            raise ValueError('Waveform crosses splits')
    a.output.write_text(json.dumps(admitted, ensure_ascii=False, indent=2)+'\n')
    a.output.with_suffix('.quarantine.json').write_text(json.dumps(quarantined, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'admitted': len(admitted), 'quarantined': len(quarantined),
        'real_child_claim': False, 'gold_phoneme_alignment': False}))


if __name__ == '__main__':
    main()
