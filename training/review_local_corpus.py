#!/usr/bin/env python3
"""Offline ASR sanity check for fictional synthesis only, never family audio.

An exact transcript screen checks content, not precise tone, age or voice identity.
It cannot establish human wake performance. No reference recordings or hotwords.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from review_google_corpus import normalize


def validate(rows,root,protected):
    for row in rows:
        if row.get('source') not in {'Google-Gemini-TTS-synthetic','Qwen3-TTS-synthetic-local','Google-TTS-level-tone-synthetic','Google-TTS-incomplete-prefix','TTS-matched-incomplete-prefix'} or not row.get('synthetic') or row.get('evaluation_only') or row.get('real_child') or row.get('reference_audio_used') or row.get('family_inputs_used'):
            raise ValueError('Only fictional synthesis without reference audio is eligible')
        p=(root/row['path']).resolve()
        if not p.is_relative_to(root.resolve()):raise ValueError('Synthetic path escapes corpus')
        digest=hashlib.sha256(p.read_bytes()).hexdigest()
        if digest in protected:raise ValueError('Protected household audio is ineligible')
        if digest!=row['sha256']:raise ValueError('Synthetic audio hash mismatch')
        if row.get('english_phonetic_surface') and (row['text'] not in {'Ni hao, pee coo.','Ni hao! Pee koo!'} or row['label']!=1 or row.get('expected_spoken_transcript')!='你好皮酷'):
            raise ValueError('Unknown English phonetic target surface')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--protected-hashes',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--prior-review',type=Path)
    a=p.parse_args();os.umask(0o077)
    rows=json.loads(a.manifest.read_text());protected=set(json.loads(a.protected_hashes.read_text())['audio_sha256'].values())
    validate(rows,a.manifest.parent,protected)
    prior={r['sha256']:r for r in json.loads(a.prior_review.read_text())} if a.prior_review and a.prior_review.exists() else {}
    cached={r['sha256']:r for r in json.loads(a.output.read_text())} if a.output.exists() else {}
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    import mlx.core as mx
    from mlx_audio.stt.utils import load_model
    mx.set_cache_limit(128*1024*1024);model=load_model(str(a.model.resolve()));result=[]
    for row in rows:
        if row['sha256'] in cached:
            record={**cached[row['sha256']]}
            approved=content_approved(row,record['transcript'])
            previous=prior.get(row['sha256'])
            prior_approved=normalize(previous['transcript'])==normalize(row['text']) if previous else None
            record.update(approved=approved and prior_approved is not False,local_approved=approved,prior_approved=prior_approved,rule='accepted-pi-ku-and-negative-pi-ke-homophones-v5-no-tone-verification')
        else:
            response=model.generate(str((a.manifest.parent/row['path']).resolve()),max_tokens=96,temperature=0,verbose=False)
            transcript=response.text.strip()
            approved=content_approved(row,transcript)
            previous=prior.get(row['sha256'])
            record=dict(sha256=row['sha256'],path=row['path'],label=row['label'],transcript=transcript,
                approved=approved and (not previous or previous.get('approved',False)),local_approved=approved,
                prior_approved=previous.get('approved') if previous else None,
                method='offline-Qwen3-ASR-content-screen-not-phonetic-or-human-validation',model=a.model.name,
                rule='accepted-pi-ku-and-negative-pi-ke-homophones-v5-no-tone-verification')
        result.append(record);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'reviewed':len(result),'approved':sum(r['approved'] for r in result),'label':row['label'],'style':row.get('synthetic_style')}),flush=True)
        mx.clear_cache()


def content_approved(row,transcript):
    if row.get('english_phonetic_surface'):
        if row['label']!=1 or row.get('expected_spoken_transcript')!='你好皮酷' or row.get('text') not in {'Ni hao, pee coo.','Ni hao! Pee koo!'}:return False
        # Match the complete utterance, keeping unexpected English words
        # visible instead of stripping them with Chinese punctuation cleanup.
        text=re.sub(r'\b(?:ni[\s-]*hao|knee[\s-]*how)\b','你好',transcript,flags=re.I)
        text=re.sub(r'\b(?:pee[\s-]*(?:coo|koo)|pikoo|piku|peekoo)\b','皮酷',text,flags=re.I)
        if re.search('[A-Za-z0-9]',text):return False
        return normalize(text)=='你好皮酷'
    normalized=normalize(transcript)
    if row['label']==0 and normalize(row.get('text',''))=='你好皮克':
        # Chinese ASR spelling does not verify lexical tone. These complete
        # pi-ke variants all remain non-targets; never admit a pi-ku name,
        # missing greeting or added speech through this narrow exception.
        return normalized in {'你好皮克','你好匹克','你好皮可','你好批克',
                              '你好批可','你好披克','你好披可','你好匹可'}
    if row.get('source')=='TTS-matched-incomplete-prefix':
        prefixes={'你','你好'}|{'你好'+c for c in '皮披批匹癖痞屁坯'}
        return row['label']==0 and normalized in prefixes
    if row.get('source')=='Google-TTS-incomplete-prefix':
        return row['label']==0 and bool(normalized) and '你好皮酷' not in normalized
    return normalized==normalize(row['text'])


if __name__=='__main__':main()
