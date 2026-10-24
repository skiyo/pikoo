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
import random
import ssl
import time
from urllib.error import HTTPError,URLError
from urllib.request import build_opener, ProxyHandler, Request
import wave
import numpy as np
from corpus_ancestry import parents


def post_json(opener,request,timeout=55,retries=0,retry_delay=65,sleep=time.sleep,
              capacity_retries=0,capacity_delay=65,jitter=random.random):
    """Explicit bounded transport/503 retry budgets; quota/auth never retry."""
    if not 10<=timeout<=180 or not 0<=retries<=3 or (retries and not 65<=retry_delay<=600):
        raise ValueError('Invalid request timeout or low-rate network retry bounds')
    if not 0<=capacity_retries<=3 or (capacity_retries and not 65<=capacity_delay<=600):
        raise ValueError('Invalid bounded capacity retry budget')
    transport_attempt=capacity_attempt=0
    while True:
        try:
            with opener.open(request,timeout=timeout) as response:return json.load(response)
        except HTTPError as error:
            if error.code!=503 or capacity_attempt>=capacity_retries:
                raise
            capacity_attempt+=1
            wait=min(600.,capacity_delay*2**(capacity_attempt-1)*(1+.1*jitter()))
            header=error.headers.get('Retry-After') if error.headers else None
            if header is not None:
                try:minimum=float(header)
                except (ValueError,TypeError):raise error
                if not 0<=minimum<=600:raise error
                wait=max(wait,minimum)
            if error.fp:error.close()
            print(json.dumps({'phase':'temporary-capacity-retry','http_status':503,
                'attempt':capacity_attempt,'maximum_retries':capacity_retries,'wait_seconds':wait}),flush=True)
            # Keep waits individually bounded so callers can remain responsive.
            remaining=wait
            while remaining>0:
                part=min(60.,remaining);sleep(part);remaining-=part
        except (TimeoutError,URLError,ConnectionError,ssl.SSLError) as error:
            reason=error.reason if isinstance(error,URLError) else error
            if isinstance(reason,ssl.SSLCertVerificationError) or transport_attempt>=retries:raise
            transport_attempt+=1
            print(json.dumps({'phase':'transient-network-retry','attempt':transport_attempt,
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


def validated_cache(rows, prior, model, *, require_independent=False):
    expected = {row['sha256']: row for row in rows}
    cached = {}
    for review in prior:
        digest = review['sha256']
        if (digest not in expected or digest in cached or review.get('model') != model
                or review.get('label') != expected[digest]['label']
                or not isinstance(review.get('transcript'), str)):
            raise ValueError('Review cache model, recording, label or uniqueness mismatch')
        if require_independent and (review.get('admission_eligible') is not True
                                    or review.get('diagnostic_only') is not False):
            raise ValueError('Cache lacks verified single-file provenance; preserve it and use a new output')
        cached[digest] = review
    return cached


def write_cache(path, rows, cached):
    """Preserve all known reviews, including later rows, with atomic replacement."""
    records = [cached[row['sha256']] for row in rows if row['sha256'] in cached]
    temporary = path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2))
    temporary.replace(path)


def validate(rows, root, protected, allow_local_synthetic=False):
    """Only declared fictional synthesis may leave the machine for review."""
    root = root.resolve()
    allowed = {'Google-Gemini-TTS-synthetic'}
    if allow_local_synthetic:
        allowed.update({'Qwen3-TTS-synthetic-local', 'Google-TTS-level-tone-synthetic'})
    for row in rows:
        if (row.get('source') not in allowed or not row.get('synthetic')
                or row.get('evaluation_only') or row.get('frozen_holdout')
                or row.get('reference_audio_used') or row.get('family_inputs_used') or row.get('real_child')):
            raise ValueError('Only fictional generated TTS without protected/reference audio may be uploaded')
        if row['source'] == 'Google-TTS-level-tone-synthetic' and not str(row.get('source_terms', '')).startswith('https://ai.google.dev/'):
            raise ValueError('Level-tone synthesis requires its Google source record')
        if parents(row) & protected:
            raise ValueError('Protected source recording cannot be uploaded through a derivative')
        path = (root/row['path']).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Generated audio path escapes corpus directory')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in protected:
            raise ValueError('Protected household/sealed audio must not be uploaded')
        if digest != row['sha256']:
            raise ValueError('Synthetic audio hash mismatch')


def content_matches(text, transcript):
    # Do not let punctuation cleanup silently erase extra spoken English or
    # digits. Only the already-supported complete name may be normalized away.
    remaining = re.sub(r'pikoo|piku|pee[- ](?:koo|coo)', '', transcript, flags=re.I)
    return not re.search('[A-Za-z0-9]', remaining) and normalize(transcript) == normalize(text)


def review_request(model, audio_data, count):
    if not 1 <= count <= 8:
        raise ValueError('Invalid transcript batch size')
    prompt = ('Transcribe the speech verbatim, including any Chinese-English mixed speech and English names. '
              'Do not correct words or infer intended names. It contains '
              + str(count) + ' separate utterances separated by silence. Return a JSON array '
              'of strings, one string per utterance, in original order. Do not add explanations or merge repeats.')
    if model == 'gemini-3.8-flash':
        # The documented 3.8 audio-understanding interface uses Interactions.
        # Keep utterance text out of the prompt and disable stored interactions.
        return ('https://generativelanguage.googleapis.com/v1beta/interactions', {
            'model': model, 'store': False,
            'input': [{'type': 'user_input', 'content': [
                {'type': 'text', 'text': prompt},
                {'type': 'audio', 'data': audio_data, 'mime_type': 'audio/wav'}]}],
            'response_format': {'type': 'text', 'mime_type': 'application/json',
                'schema': {'type': 'array', 'items': {'type': 'string'}, 'minItems': count, 'maxItems': count}},
            'generation_config': {'max_output_tokens': 1200, 'thinking_level': 'low'}})
    if model in {'gemini-2.5-flash','gemini-3.1-flash-lite'}:
        config = {'responseMimeType': 'application/json', 'maxOutputTokens': 1200}
        if model == 'gemini-2.5-flash':
            config.update(temperature=0,thinkingConfig={'thinkingBudget':0})
        else:
            config.update(thinkingConfig={'thinkingLevel':'minimal'},
                responseJsonSchema={'type':'array','items':{'type':'string'},'minItems':count,'maxItems':count})
        return ('https://generativelanguage.googleapis.com/v1beta/models/' + model + ':generateContent', {
            'contents': [{'parts': [{'text': prompt},
                {'inlineData': {'mimeType': 'audio/wav', 'data': audio_data}}]}],
            'generationConfig': config})
    raise ValueError('Unsupported content review model')


def review_text(model, response):
    if model == 'gemini-3.8-flash':
        if response.get('status') != 'completed':
            raise ValueError('Incomplete ASR interaction')
        chunks = [part['text'] for step in response.get('steps', [])
                  if step.get('type') == 'model_output' for part in step.get('content', [])
                  if part.get('type') == 'text' and isinstance(part.get('text'), str)]
        if not chunks:
            raise ValueError('ASR interaction has no model text')
        return ''.join(chunks)
    if model in {'gemini-2.5-flash','gemini-3.1-flash-lite'}:
        candidate = response['candidates'][0]
        if candidate.get('finishReason') != 'STOP':
            raise ValueError('Incomplete ASR generation')
        return ''.join(part.get('text', '') for part in candidate['content']['parts'] if not part.get('thought'))
    raise ValueError('Unsupported content review model')


def file_review_request(model, clips):
    """Keep each recording in its own media part, identified without labels.

    Unlike concatenation, a clip's identity does not depend on detecting a
    silence boundary or counting repeated utterances. ASR remains a content
    screen, not a proof of tone, age or human wake performance.
    """
    if model not in {'gemini-3.1-flash-lite', 'gemini-3.8-flash'} or not 1 <= len(clips) <= 8:
        raise ValueError('Separate-file review requires1..8 clips and an explicit supported model')
    ids = [identifier for identifier, data in clips]
    if (len(set(ids)) != len(ids) or any(not re.fullmatch('[0-9a-f]{64}', key) for key in ids)
            or any(not isinstance(data, str) or not data for key, data in clips)):
        raise ValueError('Expected unique audio hashes and nonempty inline data')
    prompt = ('Transcribe each separate audio file verbatim. Include Chinese-English mixed speech '
              'and English names. Do not correct words, infer intended names, copy speech between '
              'files, or infer missing syllables. Each file is introduced by its clip_id. '
              'Return one JSON object mapping each exact clip_id to only that file\'s transcript. '
              'Do not add keys or explanations. If a file has no speech, return an empty string for it.')
    parts = [{'text': prompt}]
    for identifier, data in clips:
        parts.extend([{'text': 'clip_id: ' + identifier},
                      {'inlineData': {'mimeType': 'audio/wav', 'data': data}}])
    schema = {'type': 'object', 'properties': {key: {'type': 'string'} for key in ids},
              'required': ids, 'additionalProperties': False}
    if model == 'gemini-3.8-flash':
        content = []
        for part in parts:
            if 'text' in part:
                content.append({'type': 'text', 'text': part['text']})
            else:
                content.append({'type': 'audio', 'mime_type': 'audio/wav',
                                'data': part['inlineData']['data']})
        return ('https://generativelanguage.googleapis.com/v1beta/interactions', {
            'model': model, 'store': False, 'input': content,
            'response_format': {'type': 'text', 'mime_type': 'application/json', 'schema': schema},
            'generation_config': {'max_output_tokens': 2400, 'thinking_level': 'low'}})
    return ('https://generativelanguage.googleapis.com/v1beta/models/' + model + ':generateContent',
            {'contents': [{'parts': parts}], 'generationConfig': {
                'responseMimeType': 'application/json', 'responseJsonSchema': schema,
                'maxOutputTokens': 2400, 'thinkingConfig': {'thinkingLevel': 'minimal'}}})


def checked_file_transcripts(text, identifiers):
    if not identifiers or len(set(identifiers)) != len(identifiers):
        raise ValueError('Expected unique file identities')

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate ASR file identity')
            result[key] = value
        return result
    records = json.loads(text, object_pairs_hook=unique_object)
    if (not isinstance(records, dict) or set(records) != set(identifiers)
            or not all(isinstance(value, str) for value in records.values())):
        raise ValueError('ASR file identities or transcript types differ')
    return [records[key] for key in identifiers]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--key-file', type=Path, required=True)
    p.add_argument('--proxy')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--model', default='gemini-3.8-flash', choices=['gemini-3.8-flash', 'gemini-2.5-flash','gemini-3.1-flash-lite'])
    p.add_argument('--interval', type=float, default=15, help='Seconds between ASR requests')
    p.add_argument('--batch-size', type=int, choices=range(1,9), default=1, help='Single-file admission by default; multiple files require diagnostic-only opt-in')
    p.add_argument('--diagnostic-batches',action='store_true',help='Allow contextual multi-audio experiments; their observations are ineligible for TRAIN admission')
    p.add_argument('--separate-files', action='store_true', help='Per-file media parts and exact hash-keyed responses with explicitly selected3.1Lite or3.8Flash')
    p.add_argument('--request-timeout',type=float,default=55,help='Bounded API read timeout, 10..180 seconds')
    p.add_argument('--network-retries',type=int,default=0,help='0..3 retries for transport faults only; HTTP/quota/auth errors still stop')
    p.add_argument('--network-retry-delay',type=float,default=65,help='65..600 seconds when transport retries are explicitly enabled')
    p.add_argument('--capacity-retries',type=int,default=0,help='Explicit0..3 retries for503capacity errors only; auth/quota errors always stop')
    p.add_argument('--capacity-retry-delay',type=float,default=65,help='65..600 second initial503backoff, exponential with jitter and a600second ceiling')
    p.add_argument('--allow-local-synthetic',action='store_true',help='Explicitly permit hash-checked fictional local Qwen TTS; never reference audio')
    p.add_argument('--protected-hashes',type=Path,help='Required protected household hash ledger when local synthesis is enabled')
    a = p.parse_args()
    if a.interval < 0:
        raise ValueError('interval must be nonnegative')
    if a.batch_size>1 and not a.diagnostic_batches:
        raise ValueError('Multi-audio context can alter near-word transcripts; admission requires one file per request')
    if a.separate_files and a.model not in {'gemini-3.1-flash-lite', 'gemini-3.8-flash'}:
        raise ValueError('Separate-file mode requires an explicit supported model')
    os.umask(0o077)
    rows = json.loads(a.manifest.read_text())
    if a.allow_local_synthetic and not a.protected_hashes:raise ValueError('Local synthetic review requires a household exclusion ledger')
    protected=set(json.loads(a.protected_hashes.read_text())['audio_sha256'].values()) if a.protected_hashes else set()
    validate(rows, a.manifest.parent, protected, a.allow_local_synthetic)
    key = next(line.split('=', 1)[1].strip().strip('\"\'') for line in a.key_file.read_text().splitlines()
               if line.startswith(('GOOGLE_API_KEY=', 'GEMINI_API_KEY=')))
    opener = build_opener(ProxyHandler({'http': a.proxy, 'https': a.proxy} if a.proxy else {}))
    report = []
    prior = json.loads(a.output.read_text()) if a.output.exists() else []
    cached = validated_cache(rows, prior, a.model, require_independent=not a.diagnostic_batches)
    for start in range(0, len(rows), a.batch_size):
        group = rows[start:start + a.batch_size]
        if all(r['sha256'] in cached for r in group):
            for row in group:
                reviewed = {**cached[row['sha256']]}
                reviewed['approved'] = content_matches(row['text'], reviewed['transcript'])
                reviewed['rule'] = 'exact-transcript-with-target-homophones-v3-no-extra-Latin'
                report.append(reviewed)
                cached[row['sha256']] = reviewed
            continue
        # Never re-query or overwrite an existing recording's review merely
        # because another member of its original batch is still missing.
        group = [row for row in group if row['sha256'] not in cached]
        audio = []
        separate = []
        for row in group:
            with wave.open(str(a.manifest.parent / row['path'])) as w:
                if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, 16000):
                    raise ValueError('Expected generated PCM16 16kHz audio')
                audio.append(np.frombuffer(w.readframes(w.getnframes()), '<i2'))
                audio.append(np.zeros(16000, '<i2'))
            if a.separate_files:
                separate.append((row['sha256'], base64.b64encode((a.manifest.parent / row['path']).read_bytes()).decode()))
        out = io.BytesIO()
        with wave.open(out, 'wb') as w:
            w.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            w.writeframes(np.concatenate(audio).tobytes())
        if a.separate_files:
            url, payload = file_review_request(a.model, separate)
        else:
            url, payload = review_request(a.model, base64.b64encode(out.getvalue()).decode(), len(group))
        request = Request(url,
            data=json.dumps(payload).encode(), headers={'x-goog-api-key': key, 'Content-Type': 'application/json'})
        try:
            data=post_json(opener,request,a.request_timeout,a.network_retries,a.network_retry_delay,
                           capacity_retries=a.capacity_retries,capacity_delay=a.capacity_retry_delay)
        except HTTPError as error:
            try:
                decoded=json.loads(error.read()).get('error',{})
                safe={'model':a.model,'code':error.code,'status':decoded.get('status'),'details':decoded.get('details',[]),'retry_after':error.headers.get('Retry-After')}
                a.output.with_name('review-api-error.json').write_text(json.dumps(safe,indent=2)+'\n')
            except (ValueError,OSError):pass
            raise RuntimeError(f'Synthetic review HTTP {error.code}; stopped without further requests') from None
        except (TimeoutError,URLError,ConnectionError,ssl.SSLError) as error:
            safe={'model':a.model,'status':'transport-failure','error_type':type(error).__name__,
                  'cached_reviews':len(cached),'request_timeout':a.request_timeout}
            a.output.with_name('review-api-error.json').write_text(json.dumps(safe,indent=2)+'\n')
            raise
        text = review_text(a.model, data)
        transcripts = checked_file_transcripts(text, [row['sha256'] for row in group]) if a.separate_files else checked_transcripts(text, len(group))
        for row, transcript in zip(group, transcripts):
            approved = content_matches(row['text'], transcript)
            report.append({'sha256': row['sha256'], 'path': row['path'], 'label': row['label'],
                'transcript': transcript, 'approved': approved, 'model': a.model,
                'diagnostic_only':len(group)>1,'admission_eligible':len(group)==1,
                'rule': 'exact-transcript-with-target-homophones-v3-no-extra-Latin',
                'method': 'Google-ASR-separate-file-hash-identified-screen' if a.separate_files else 'Google-ASR-sanity-check-not-human-review'})
            cached[row['sha256']] = report[-1]
        write_cache(a.output, rows, cached)
        print(json.dumps({'reviewed': len(cached), 'approved': sum(r['approved'] for r in cached.values())}), flush=True)
        if start + a.batch_size < len(rows):
            time.sleep(a.interval)
    write_cache(a.output, rows, cached)


if __name__ == '__main__':
    main()
