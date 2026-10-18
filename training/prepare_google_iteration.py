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
import wave
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
    p.add_argument('--reviewed-prefixes',type=Path,nargs='*',default=[],help='Content-reviewed incomplete fictional TTS phrases as hard negatives')
    p.add_argument('--context-frames',type=int,default=0,help='If set, exclude TRAIN positives that cannot fit whole with 300ms lead, 120ms tail and 0.88 minimum speed jitter; validation is unchanged')
    p.add_argument('--quarantine-training-negatives',nargs='*',default=[],help='Explicit ambiguous synthetic near-name texts to withhold from TRAIN; legacy validation remains unchanged')
    a = p.parse_args()
    os.umask(0o077)
    if not 1 <= a.mac_positives_per_voice <= 64:
        raise ValueError('Invalid historical positive cap')
    if a.context_frames and (a.context_frames<150 or a.context_frames%3):
        raise ValueError('Context must contain at least 150 frames and be divisible by three')
    protected = set(json.loads(a.excluded_audio_hashes.read_text())['audio_sha256'].values())
    rows = []
    historical_positives = defaultdict(list)
    too_long_train_positives=[]
    ambiguous_train_negatives=[]
    ambiguous_texts={normalize(text) for text in a.quarantine_training_negatives}

    def append(row, manifest):
        if row.get('evaluation_only') or str(row.get('source', '')).startswith('private-'):
            raise ValueError('External human recordings are evaluation-only')
        path = (manifest.parent / row['path']).resolve()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in protected:
            raise ValueError('Protected human recording cannot enter model development')
        if row.get('sha256') and digest != row['sha256']:
            raise ValueError('Source audio hash mismatch')
        if row['split']=='train' and not row['label'] and row.get('synthetic') and normalize(row.get('text','')) in ambiguous_texts:
            ambiguous_train_negatives.append(digest)
            return
        if a.context_frames and row['split']=='train' and row['label']:
            with wave.open(str(path)) as audio:
                if (audio.getnchannels(),audio.getsampwidth(),audio.getframerate())!=(1,2,16000):
                    raise ValueError('Expected mono 16kHz PCM16 target')
                samples=row.get('wake_end_sample',audio.getnframes())
                if not 0<samples<=audio.getnframes():raise ValueError('Invalid target endpoint')
            maximum=((a.context_frames+2)*160-4800-1920)*.88
            if samples>maximum:
                too_long_train_positives.append({'sha256':digest,'source':row.get('source'),'samples':samples})
                return
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
            if row.get('source') not in {'Google-TTS-incomplete-prefix','TTS-matched-incomplete-prefix'} or row['label']!=0 or not row.get('synthetic') or row.get('reference_audio_used') or row.get('family_inputs_used') or row.get('real_child'):
                raise ValueError('Prefix negatives require fictional TTS derivatives')
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
              'context_frames':a.context_frames,'too_long_train_positives_excluded':len(too_long_train_positives),'validation_context_exclusions':0,
              'ambiguous_training_negatives_quarantined':len(ambiguous_train_negatives),'legacy_validation_label_exclusions':0,
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
