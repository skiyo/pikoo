#!/usr/bin/env python3
"""Transcript sanity check for newly generated TTS only, never household audio.

Automated ASR is a label-quality screen, not independent human validation.
Only hash-verified fictional synthesis is eligible for upload to Gemini;
local Qwen synthesis requires an explicit opt-in and a protected-audio ledger.
"""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import ssl
import time
from urllib.error import HTTPError,URLError
from urllib.request import build_opener, ProxyHandler, Request
import wave
import numpy as np


def post_json(opener,request,timeout=55,retries=0,retry_delay=65,sleep=time.sleep):
    """Bounded retries for transport faults only; never retry API/quota errors."""
    if not 10<=timeout<=180 or not 0<=retries<=3 or (retries and not 65<=retry_delay<=600):
        raise ValueError('Invalid request timeout or low-rate network retry bounds')
    for attempt in range(retries+1):
        try:
            with opener.open(request,timeout=timeout) as response:return json.load(response)
        except HTTPError:raise
        except (TimeoutError,URLError,ConnectionError,ssl.SSLError) as error:
            reason=error.reason if isinstance(error,URLError) else error
            if isinstance(reason,ssl.SSLCertVerificationError) or attempt==retries:raise
            print(json.dumps({'phase':'transient-network-retry','attempt':attempt+1,
                'wait_seconds':retry_delay,'error_type':type(reason).__name__}),flush=True)
            sleep(retry_delay)


def normalize(text):
    text = re.sub(r'pikoo|piku|pee[- ](?:koo|coo)', '皮酷', text, flags=re.IGNORECASE)
    text = text.translate(str.maketrans('庫褲給講個裡哪兒', '库裤给讲个里哪儿'))
    text=re.sub(r'[^\u4e00-\u9fff]', '', text)
    # ASR spelling cannot establish lexical tone. The accepted name covers the
    # pi/ku syllables with natural intonation; gu, gou, ke and qiu stay distinct.
    return re.sub(r'[皮披批匹癖痞屁坯][酷裤库枯哭苦窟]', '皮酷', text)


def checked_transcripts(text, count):
    transcripts = json.loads(text)
    if not isinstance(transcripts, list) or len(transcripts) != count or not all(isinstance(t, str) for t in transcripts):
        raise ValueError('ASR utterance count mismatch')
    return transcripts


def content_matches(text, transcript):
    # Do not let punctuation cleanup silently erase extra spoken English or
    # digits. Only the already-supported complete name may be normalized away.
    remaining = re.sub(r'pikoo|piku|pee[- ](?:koo|coo)', '', transcript, flags=re.I)
    return not re.search('[A-Za-z0-9]', remaining) and normalize(transcript) == normalize(text)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--key-file', type=Path, required=True)
    p.add_argument('--proxy')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--model', default='gemini-3.8-flash', choices=['gemini-3.8-flash', 'gemini-2.5-flash'])
    p.add_argument('--interval', type=float, default=15, help='Seconds between ASR requests')
    p.add_argument('--batch-size', type=int, choices=range(1,9), default=8, help='1..8 utterances per request; use 1 to avoid multi-utterance alignment ambiguity')
    p.add_argument('--request-timeout',type=float,default=55,help='Bounded API read timeout, 10..180 seconds')
    p.add_argument('--network-retries',type=int,default=0,help='0..3 retries for transport faults only; HTTP/quota/auth errors still stop')
    p.add_argument('--network-retry-delay',type=float,default=65,help='65..600 seconds when transport retries are explicitly enabled')
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
    for start in range(0, len(rows), a.batch_size):
        group = rows[start:start + a.batch_size]
        if all(r['sha256'] in cached for r in group):
            for row in group:
                reviewed = {**cached[row['sha256']]}
                reviewed['approved'] = content_matches(row['text'], reviewed['transcript'])
                reviewed['rule'] = 'exact-transcript-with-target-homophones-v3-no-extra-Latin'
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
            data=post_json(opener,request,a.request_timeout,a.network_retries,a.network_retry_delay)
        except HTTPError as error:
            try:
                decoded=json.loads(error.read()).get('error',{})
                safe={'code':error.code,'status':decoded.get('status'),'details':decoded.get('details',[]),'retry_after':error.headers.get('Retry-After')}
                a.output.with_name('review-api-error.json').write_text(json.dumps(safe,indent=2)+'\n')
            except (ValueError,OSError):pass
            raise RuntimeError(f'Synthetic review HTTP {error.code}; stopped without further requests') from None
        text = ''.join(p.get('text', '') for p in data['candidates'][0]['content']['parts'])
        transcripts = checked_transcripts(text, len(group))
        for row, transcript in zip(group, transcripts):
            approved = content_matches(row['text'], transcript)
            report.append({'sha256': row['sha256'], 'path': row['path'], 'label': row['label'],
                'transcript': transcript, 'approved': approved, 'model': a.model,
                'rule': 'exact-transcript-with-target-homophones-v3-no-extra-Latin',
                'method': 'Google-ASR-sanity-check-not-human-review'})
        a.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps({'reviewed': len(report), 'approved': sum(r['approved'] for r in report)}), flush=True)
        if start + a.batch_size < len(rows):
            time.sleep(a.interval)


if __name__ == '__main__':
    main()
