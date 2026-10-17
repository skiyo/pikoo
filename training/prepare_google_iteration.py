#!/usr/bin/env python3
"""Merge label-reviewed Google voices with licensed speech, excluding family audio.

Preserves voice splits. An entire synthesized batch is rejected when any label
review disagrees, so a dropped utterance cannot silently shift all later labels.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
from review_google_corpus import normalize


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--previous', type=Path, required=True)
    p.add_argument('--google','--reviewed-synthetic',dest='google', type=Path, nargs='+', required=True)
    p.add_argument('--real-negatives', type=Path, required=True)
    p.add_argument('--excluded-audio-hashes', type=Path, required=True, help='Private protected-recording ledger')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--mac-positives-per-voice', type=int, default=8)
    p.add_argument('--drop-historical-positives',action='store_true',help='Remove macOS/self-test training positives; keep historical development regression')
    p.add_argument('--validation-challenge',type=Path,nargs='*',default=[],help='Reviewed synthetic validation rows only; never add their training rows')
    p.add_argument('--reviewed-prefixes',type=Path,nargs='*',default=[],help='Content-reviewed incomplete Google wake phrases as hard negatives')
    a = p.parse_args()
    os.umask(0o077)
    if not 1 <= a.mac_positives_per_voice <= 64:
        raise ValueError('Invalid historical positive cap')
    protected = set(json.loads(a.excluded_audio_hashes.read_text())['audio_sha256'].values())
    rows = []
    historical_positives = defaultdict(list)

    def append(row, manifest):
        if row.get('evaluation_only') or str(row.get('source', '')).startswith('private-'):
            raise ValueError('External human recordings are evaluation-only')
        path = (manifest.parent / row['path']).resolve()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in protected:
            raise ValueError('Protected human recording cannot enter model development')
        if row.get('sha256') and digest != row['sha256']:
            raise ValueError('Source audio hash mismatch')
        rows.append({**row, 'path': os.path.relpath(path, a.output.resolve()), 'sha256': digest})

    for row in json.loads(a.previous.read_text()):
        if row['split'] == 'test':
            continue  # Neither the old test corpus nor household test is development input.
        if row['split'] == 'train' and row['label'] and row.get('source', '').startswith(('macOS', 'known-self-test')):
            if a.drop_historical_positives:continue
            historical_positives[row.get('speaker', row.get('voice', row['group']))].append(row)
        else:
            append(row, a.previous)
    for group in historical_positives.values():
        selected = sorted(group, key=lambda r: hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest())
        for row in selected[:a.mac_positives_per_voice]:
            append(row, a.previous)
    rejected = 0
    for manifest in a.google:
        candidates = json.loads(manifest.read_text())
        if any(r.get('source') not in {'Google-Gemini-TTS-synthetic','Qwen3-TTS-synthetic-local','Google-TTS-level-tone-synthetic'} or not r.get('synthetic') or r.get('reference_audio_used') or r.get('family_inputs_used') or r.get('real_child') for r in candidates):
            raise ValueError('Reviewed inputs must be fictional synthetic TTS without reference audio')
        review = {r['sha256']: r for r in json.loads((manifest.parent / 'review.json').read_text())}
        batches = defaultdict(list)
        for row in candidates:
            batches[row.get('batch_id', row['sha256'])].append(row)
        for batch in batches.values():
            valid = all(r['sha256'] in review and review[r['sha256']].get('approved',True) and
                        normalize(review[r['sha256']]['transcript']) == normalize(r['text']) for r in batch)
            if not valid:
                rejected += len(batch)
                continue
            for row in batch:
                if row['split'] != 'test':
                    append({**row, 'label_review': 'exact-ASR-screen-not-human-validation'}, manifest)
    for row in json.loads(a.real_negatives.read_text()):
        if row['label'] or row['split'] != 'train':
            raise ValueError('Unknown-speaker real corpus must contain training negatives only')
        append(row, a.real_negatives)
    challenge_count=0
    for manifest in a.validation_challenge:
        reviews={r['sha256']:r for r in json.loads((manifest.parent/'review.json').read_text())}
        for row in json.loads(manifest.read_text()):
            if row['split']!='validation':continue
            if row.get('source') not in {'Qwen3-TTS-synthetic-local','Google-Gemini-TTS-synthetic'} or not row.get('synthetic') or row.get('reference_audio_used') or row.get('family_inputs_used') or row.get('real_child'):
                raise ValueError('Development challenges require fictional synthetic audio')
            checked=reviews.get(row['sha256'],{})
            if checked.get('approved') and normalize(checked.get('transcript',''))==normalize(row['text']):
                append({**row,'usage':'validation challenge only; not training'},manifest);challenge_count+=1
    prefix_count=0
    for manifest in a.reviewed_prefixes:
        reviews={r['sha256']:r for r in json.loads((manifest.parent/'review.json').read_text())}
        for row in json.loads(manifest.read_text()):
            if row.get('source')!='Google-TTS-incomplete-prefix' or row['label']!=0 or not row.get('synthetic') or row.get('reference_audio_used') or row.get('family_inputs_used') or row.get('real_child'):
                raise ValueError('Prefix negatives require fictional Google derivatives')
            if row['split']=='test':continue
            checked=reviews.get(row['sha256'],{})
            heard=normalize(checked.get('transcript',''))
            if checked.get('approved') and heard and '你好皮酷' not in heard:
                append({**row,'hard_negative':True},manifest);prefix_count+=1
    identities = {}
    waveforms = {}
    unique = []
    for row in rows:
        group = row.get('speaker', row.get('voice', row['group']))
        if group in identities and identities[group] != row['split']:
            raise ValueError('Speaker identity crosses splits')
        identities[group] = row['split']
        if row['sha256'] in waveforms:
            if waveforms[row['sha256']] != row['split']:
                raise ValueError('Waveform crosses splits')
            continue
        waveforms[row['sha256']] = row['split']
        unique.append(row)
    a.output.mkdir(parents=True, exist_ok=True)
    path = a.output / 'manifest.json'
    path.write_text(json.dumps(unique, ensure_ascii=False, indent=2))
    report = {'status': 'development-data-no-household-audio', 'rejected_google_rows': rejected,
              'historical_training_positives_removed':a.drop_historical_positives,'synthetic_validation_challenges':challenge_count,'reviewed_prefix_negatives':prefix_count,
              'protected_human_hashes': len(protected),
              'sources': dict(Counter(r.get('source') for r in unique)),
              'counts': {s: {'positive': sum(r['split'] == s and r['label'] == 1 for r in unique),
                            'negative': sum(r['split'] == s and r['label'] == 0 for r in unique),
                            'real_child': sum(r['split'] == s and bool(r.get('real_child')) for r in unique)}
                         for s in ['train', 'validation']},
              'manifest_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    (a.output / 'preparation-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
