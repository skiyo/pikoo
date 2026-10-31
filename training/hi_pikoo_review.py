#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Blind offline ASR screen of NEW fictional Hi Pikoo synthesis only.

ASR agreement is content evidence, never proof of /u/ vs /o/, child age,
speaker identity or hardware accuracy. It NEVER admits samples to training.
No model downloads, reference recordings, household input or cloud calls.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re


def normalized(text):
    text = text.lower()
    # Preserve different vowels/consonants: piko and tikoo never become pikoo.
    text = re.sub(r'\bpee[\s-]*(?:koo|coo)\b', 'pikoo', text)
    text = re.sub(r'\b(?:peekoo|piku)\b', 'pikoo', text)
    text = re.sub(r'\b(?:pico|peeko|pee[\s-]*koh)\b', 'piko', text)
    text = re.sub(r'\b(?:tee[\s-]*koo|tiku)\b', 'tikoo', text)
    text = re.sub(r'\btico\b', 'tiko', text)
    text = text.translate(str.maketrans({'！': '!', '，': ',', '。': '.'}))
    return re.sub(r'[\s,.!?:;，。！？、\-]', '', text)


def content_match(row, transcript):
    actual = normalized(transcript)
    if row['label']:
        # ASR Hanzi choices do not establish lexical tone. The new target
        # permits natural intonation; retain exactly hai + pi + ku only.
        equivalents = {'嗨'+p+k for p in '批披皮匹坯' for k in '枯哭酷库裤窟'}
        accepted = {'hipikoo'}
        if row.get('target_contract') == 'hi-piku-piko-v2':
            accepted.add('hipiko')
        return actual in accepted or actual in equivalents
    # Exact full-utterance check; no stripping unexpected words or numbers.
    # Either vowel on a name-alone negative is still an incomplete greeting;
    # this does not relabel a full target or strip unexpected words.
    if normalized(row['text']) in {'pikoo', 'piko'}:
        return actual in {'pikoo', 'piko'}
    if normalized(row['text']) in {'hitikoo', 'hitiko'}:
        return actual in {'hitikoo', 'hitiko'}
    if normalized(row['text']) == 'hipee':
        return actual in {'hipee', 'hip'}  # ASR letter P /pi:/, still incomplete.
    return actual == normalized(row['text'])


def validate(row, root, protected):
    if (row.get('source') not in {'OpenAI-Realtime-synthetic', 'Qwen3-TTS-hi-piku-synthetic-local'} or
        not row.get('synthetic') or row.get('real_child') or
        row.get('family_inputs_used') or row.get('reference_audio_used') or
        row.get('evaluation_only') or row.get('frozen_holdout') or
        row['split'] not in {'train', 'validation'}):
        raise ValueError('Only new unsealed fictional TRAIN/DEV synthesis is eligible')
    p = (root/row['path']).resolve()
    if not p.is_relative_to(root.resolve()):
        raise ValueError('Audio path escapes new synthetic corpus')
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    if digest != row['sha256'] or digest in protected:
        raise ValueError('Hash mismatch or protected recording')
    if row.get('parent_sha256') or row.get('ancestry_parents'):
        raise ValueError('Review originals only, never unnamed derivatives')
    return p


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--asr-model', type=Path, required=True)
    p.add_argument('--protected-hashes', type=Path, required=True, action='append')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    os.umask(0o077)
    if not a.asr_model.is_dir():
        raise ValueError('An already-downloaded local ASR model is required')
    rows = json.loads(a.manifest.read_text())
    protected = set()
    for f in a.protected_hashes:
        protected.update(json.loads(f.read_text())['audio_sha256'].values())
    paths = [validate(r, a.manifest.parent, protected) for r in rows]
    prior = json.loads(a.output.read_text()) if a.output.exists() else []
    cached = {r['sha256']: r for r in prior}
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    from mlx_audio.stt.utils import load_model
    import mlx.core as mx
    mx.set_cache_limit(128*1024*1024)
    model = load_model(str(a.asr_model.resolve()))
    results = []
    for row, audio in zip(rows, paths):
        if row['sha256'] in cached:
            record = dict(cached[row['sha256']])
            agreed = content_match(row, record['transcript'])
            if agreed != record['local_content_passed']:
                record['previous_local_content_passed'] = record['local_content_passed']
                record['local_content_passed'] = agreed
                record['rule_change'] = 'exact hai-pi-ku Hanzi/Latin spelling variants; no vowel or age claim'
        else:
            # No target text, hotword, initial prompt or family audio supplied.
            reply = model.generate(str(audio), max_tokens=96,
                                   temperature=0, verbose=False)
            transcript = reply.text.strip()
            record = {'id': row.get('id', row.get('profile')), 'sha256': row['sha256'],
                'transcript': transcript,
                'local_content_passed': content_match(row, transcript),
                'generator_content_passed': content_match(row, row['transcript']) if row.get('transcript') else None,
                'pronunciation_review': 'pending-independent-phonetic-review',
                'admitted_to_training': False,
                'method': 'blind-offline-Qwen3-ASR; not a vowel/tone or real-child check'}
        results.append(record)
        temp = a.output.with_suffix('.partial')
        temp.write_text(json.dumps(results, ensure_ascii=False, indent=2)+'\n')
        temp.replace(a.output)
        print(json.dumps({'reviewed': len(results),
            'local_content_passed': sum(x['local_content_passed'] for x in results),
            'training_admitted': 0}), flush=True)
        mx.clear_cache()


if __name__ == '__main__':
    main()
