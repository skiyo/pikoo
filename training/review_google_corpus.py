#!/usr/bin/env python3
"""Transcript sanity check for newly generated TTS only, never household audio.

Automated ASR is a label-quality screen, not independent human validation.
Only hash-verified Google synthetic clips are eligible for upload to Gemini.
"""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.request import build_opener, ProxyHandler, Request
import wave
import numpy as np


def normalize(text):
    text = re.sub(r'pikoo|piku|pee[- ](?:koo|coo)', '皮酷', text, flags=re.IGNORECASE)
    text = text.translate(str.maketrans('庫褲給講個裡哪兒', '库裤给讲个里哪儿'))
    text=re.sub(r'[^\u4e00-\u9fff]', '', text)
    # ASR spelling cannot establish lexical tone. The accepted name covers the
    # pi/ku syllables with natural intonation; gu, gou, ke and qiu stay distinct.
    return re.sub(r'[皮披批匹癖痞屁坯][酷裤库枯哭苦窟]', '皮酷', text)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--key-file', type=Path, required=True)
    p.add_argument('--proxy')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--model', default='gemini-3.8-flash', choices=['gemini-3.8-flash', 'gemini-2.5-flash'])
    p.add_argument('--interval', type=float, default=15, help='Seconds between ASR requests')
    p.add_argument('--allow-local-synthetic',action='store_true',help='Explicitly permit hash-checked fictional local Qwen TTS; never reference audio')
    p.add_argument('--protected-hashes',type=Path,help='Required protected household hash ledger when local synthesis is enabled')
    a = p.parse_args()
    if a.interval < 0:
        raise ValueError('interval must be nonnegative')
    os.umask(0o077)
    rows = json.loads(a.manifest.read_text())
    if a.allow_local_synthetic and not a.protected_hashes:raise ValueError('Local synthetic review requires a household exclusion ledger')
    protected=set(json.loads(a.protected_hashes.read_text())['audio_sha256'].values()) if a.protected_hashes else set()
    for row in rows:
        allowed={'Google-Gemini-TTS-synthetic'}
        if a.allow_local_synthetic:allowed.add('Qwen3-TTS-synthetic-local')
        if row.get('source') not in allowed or not row.get('synthetic') or row.get('evaluation_only') or row.get('reference_audio_used') or row.get('family_inputs_used') or row.get('real_child'):
            raise ValueError('Only generated fictional TTS without reference/household audio may be uploaded for review')
        path = (a.manifest.parent / row['path']).resolve()
        if not path.is_relative_to(a.manifest.parent.resolve()):
            raise ValueError('Generated audio path escapes corpus directory')
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in protected:raise ValueError('Protected household audio must not be uploaded')
        if digest != row['sha256']:
            raise ValueError('Synthetic audio hash mismatch')
    key = next(line.split('=', 1)[1].strip().strip('\"\'') for line in a.key_file.read_text().splitlines()
               if line.startswith(('GOOGLE_API_KEY=', 'GEMINI_API_KEY=')))
    opener = build_opener(ProxyHandler({'http': a.proxy, 'https': a.proxy} if a.proxy else {}))
    report = []
    prior = json.loads(a.output.read_text()) if a.output.exists() else []
    cached = {r['sha256']: r for r in prior}
    for start in range(0, len(rows), 8):
        group = rows[start:start + 8]
        if all(r['sha256'] in cached for r in group):
            for row in group:
                reviewed = {**cached[row['sha256']]}
                reviewed['approved'] = normalize(reviewed['transcript']) == normalize(row['text'])
                reviewed['rule'] = 'exact-transcript-with-target-homophones-v2'
                report.append(reviewed)
            a.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
            continue
        audio = []
        for row in group:
            with wave.open(str(a.manifest.parent / row['path'])) as w:
                if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, 16000):
                    raise ValueError('Expected generated PCM16 16kHz audio')
                audio.append(np.frombuffer(w.readframes(w.getnframes()), '<i2'))
                audio.append(np.zeros(16000, '<i2'))
        out = io.BytesIO()
        with wave.open(out, 'wb') as w:
            w.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            w.writeframes(np.concatenate(audio).tobytes())
        payload = {'contents': [{'parts': [
            {'text': 'Transcribe the speech verbatim, including any Chinese-English mixed speech and English names. Do not correct words or infer intended names. It contains '
                + str(len(group)) + ' separate utterances separated by silence. Return a JSON array '
                'of strings, one string per utterance. Do not add explanations or merge repeats.'},
            {'inlineData': {'mimeType': 'audio/wav', 'data': base64.b64encode(out.getvalue()).decode()}}]}],
            'generationConfig': {'responseMimeType': 'application/json', 'temperature': 0, 'maxOutputTokens': 1200}}
        if a.model == 'gemini-2.5-flash':
            payload['generationConfig']['thinkingConfig'] = {'thinkingBudget': 0}
        request = Request('https://generativelanguage.googleapis.com/v1beta/models/' + a.model + ':generateContent',
            data=json.dumps(payload).encode(), headers={'x-goog-api-key': key, 'Content-Type': 'application/json'})
        try:
            with opener.open(request, timeout=55) as response:
                data = json.load(response)
        except HTTPError as error:
            try:
                decoded=json.loads(error.read()).get('error',{})
                safe={'code':error.code,'status':decoded.get('status'),'details':decoded.get('details',[]),'retry_after':error.headers.get('Retry-After')}
                a.output.with_name('review-api-error.json').write_text(json.dumps(safe,indent=2)+'\n')
            except (ValueError,OSError):pass
            raise RuntimeError(f'Synthetic review HTTP {error.code}; stopped without further requests') from None
        text = ''.join(p.get('text', '') for p in data['candidates'][0]['content']['parts'])
        transcripts = json.loads(text)
        if not isinstance(transcripts, list) or len(transcripts) != len(group) or not all(isinstance(t, str) for t in transcripts):
            raise ValueError('ASR utterance count mismatch')
        for row, transcript in zip(group, transcripts):
            normalized = normalize(transcript)
            approved = normalized == normalize(row['text'])
            report.append({'sha256': row['sha256'], 'path': row['path'], 'label': row['label'],
                'transcript': transcript, 'approved': approved, 'model': a.model,
                'rule': 'exact-transcript-with-target-homophones-v2',
                'method': 'Google-ASR-sanity-check-not-human-review'})
        a.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps({'reviewed': len(report), 'approved': sum(r['approved'] for r in report)}), flush=True)
        if start + 8 < len(rows):
            time.sleep(a.interval)


if __name__ == '__main__':
    main()
