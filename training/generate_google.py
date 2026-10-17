#!/usr/bin/env python3
"""Explicit, bounded Gemini TTS corpus generation; never reads user recordings.

Generated voices are synthetic, not evidence of real adult/child wake accuracy.
Uses the documented Gemini 3.8 TTS Interactions REST endpoint. The caller must
have API access and use quota permitted by their project. No paid fallback.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import os
from pathlib import Path
import time
import threading
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener
import wave

import numpy as np

MODEL = 'gemini-3.8-flash-tts'
FREE_TTS_MODELS = [MODEL, 'gemini-3.8-flash-lite-tts',
                   'gemini-3.1-flash-tts-preview', 'gemini-2.5-flash-preview-tts']
VOICES = {
    'train': ['Kore', 'Puck', 'Charon', 'Fenrir', 'Leda', 'Orus', 'Aoede', 'Zephyr'],
    'validation': ['Autonoe', 'Achernar'],
    'test': ['Gacrux', 'Algenib'],
}
STYLES = [
    'Natural conversational voice, normal speed.',
    'Casual voice, slightly fast connected speech, not an announcer.',
    'Soft everyday voice, normal speed, not whispered.',
    'Relaxed voice, slightly slow with a brief natural pause after ni hao.',
]
NEGATIVES = ['你好皮球', '你好朋友', '给我讲一个故事', '皮球在哪里']


def jobs(mixed_pronunciation=False,phonetic_spelling=False):
    """Assign voice identities to splits before any generation or augmentation."""
    rows = []
    for split, voices in VOICES.items():
        for voice in voices:
            targets=['你好皮酷','你好Pikoo','你好，Pikoo','你好皮酷'] if mixed_pronunciation else ['你好皮酷']*4
            if phonetic_spelling:targets=['你好皮酷','你好批枯','你好披哭','你好皮酷']
            for label, texts in [(1, targets), (0, NEGATIVES)]:
                for index, text in enumerate(texts):
                    style = ('Speak standard Mainland Mandarin Chinese. Read only '
                             'the exact supplied Chinese text, addressing a small pet robot. '
                             + STYLES[index])
                    pronunciation='mixed-pi1-ku1' if 'Pikoo' in text or text in {'你好批枯','你好披哭'} else 'mandarin-pi2-ku4' if label else 'non-target'
                    if 'Pikoo' in text:
                        style=('Read the Chinese greeting 你好 then the English pet name Pikoo, '
                               'pronounced PEE-koo, two clear level syllables, not pie-co and not pee-go. '
                               'Do not translate Pikoo into a Chinese word or add any extra words. '+STYLES[index])
                    elif pronunciation=='mixed-pi1-ku1':
                        style=('Read the exact Chinese text. The robot name 批枯 / 披哭 is pronounced pī kū, '
                               'both first tones, two clear level syllables, equivalent to English PEE-koo. '
                               'Do not substitute a different name or add words. '+STYLES[index])
                    rows.append(dict(split=split, voice=voice, speaker='gemini:' + voice,
                                     group='gemini:' + voice, text=text, label=label,
                                     pronunciation=pronunciation,
                                     style=style, source='Google-Gemini-TTS-synthetic',
                                     real_child=False, synthetic=True,
                                     source_terms='https://ai.google.dev/gemini-api/terms'))
    return rows


def decode_audio(response, max_seconds=15):
    if 'candidates' in response:
        candidate = response['candidates'][0]
        if candidate.get('finishReason') != 'STOP':
            raise ValueError('Legacy TTS output did not complete')
        parts = [p['inlineData'] for p in candidate.get('content', {}).get('parts', []) if 'inlineData' in p]
        if len(parts) != 1:
            raise ValueError('Expected one legacy TTS audio output')
        part = parts[0]
        raw = base64.b64decode(part['data'], validate=True)
        if raw[:4] != b'RIFF':
            if not part.get('mimeType', '').lower().startswith('audio/l16'):
                raise ValueError('Unexpected legacy TTS audio format')
            # Documented Gemini 2.5/3.1 native TTS output: PCM16, 24kHz, mono.
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as target:
                target.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
                target.writeframes(raw)
            raw = buffer.getvalue()
        response = {'status': 'completed', 'steps': [{'type': 'model_output',
            'content': [{'type': 'audio', 'data': base64.b64encode(raw).decode()}]}]}
    parts = [part for step in response.get('steps', [])
             if step.get('type') == 'model_output'
             for part in step.get('content', []) if part.get('type') == 'audio']
    if response.get('status') != 'completed' or len(parts) != 1:
        raise ValueError('Expected one complete generated audio output')
    blob = base64.b64decode(parts[0]['data'], validate=True)
    with wave.open(io.BytesIO(blob)) as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise ValueError('Expected mono PCM16 WAV')
        rate = source.getframerate()
        pcm = np.frombuffer(source.readframes(source.getnframes()), '<i2')
    if not 0.3 <= len(pcm) / rate <= max_seconds:
        raise ValueError('Generated utterance duration outside safety bounds')
    if float(np.sqrt(np.mean(pcm.astype(np.float64) ** 2))) < 20:
        raise ValueError('Generated audio is effectively silent')
    samples = resample(pcm, rate)
    return np.clip(np.rint(samples), -32768, 32767).astype('<i2')


def resample(pcm, rate):
    """Windowed-sinc anti-alias filter plus interpolation; NumPy only."""
    x = np.asarray(pcm, dtype=np.float64)
    if rate > 16000:
        positions = np.arange(-48, 49)
        cutoff = .45 * 16000 / rate
        taps = 2 * cutoff * np.sinc(2 * cutoff * positions) * np.hamming(len(positions))
        taps /= taps.sum()
        x = np.convolve(x, taps, mode='same')
    count = round(len(pcm) * 16000 / rate)
    return np.interp(np.arange(count) * rate / 16000, np.arange(len(x)), x)


def split_utterances(pcm, expected):
    """Split only on long TTS pauses; reject the whole batch if count differs."""
    frames = np.asarray(pcm[:len(pcm) // 320 * 320], dtype=np.float64).reshape(-1, 320)
    rms = np.sqrt(np.mean(frames ** 2, axis=1))
    active = np.flatnonzero(rms > max(35, float(np.percentile(rms, 15)) * 3))
    if len(active) == 0:
        raise ValueError('No speech in generated batch')
    cuts = np.flatnonzero(np.diff(active) > 25) + 1  # >500ms of silence
    groups = np.split(active, cuts)
    if len(groups) != expected:
        raise ValueError(f'Batch alignment failed: expected {expected}, found {len(groups)} utterances')
    result = []
    for group in groups:
        start = max(0, int(group[0]) * 320 - 1280)
        end = min(len(pcm), (int(group[-1]) + 1) * 320 + 1600)
        if not .3 <= (end - start) / 16000 <= 10:
            raise ValueError('Batch utterance duration outside bounds')
        result.append(pcm[start:end])
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--key-file', type=Path, required=True, help='Private KEY=VALUE file')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--proxy', help='Explicit per-process proxy; environment proxies are ignored')
    p.add_argument('--workers', type=int, default=2, choices=[1, 2])
    p.add_argument('--limit', type=int, default=96, help='Bound this invocation; cached clips cost no calls')
    p.add_argument('--interval', type=float, default=15, help='Minimum seconds between requests to respect free-tier rate limits')
    p.add_argument('--batch-voices', action='store_true', help='Eight utterances per voice/request, with strict pause alignment')
    p.add_argument('--model', choices=FREE_TTS_MODELS, default=MODEL)
    p.add_argument('--childlike-voices', nargs='*', default=[], help='Synthetic youthful delivery only; never labeled real children')
    p.add_argument('--items-per-voice', choices=[4, 8], type=int, default=8)
    p.add_argument('--voices', nargs='*', help='Optional explicit voice ordering; split assignment never changes')
    p.add_argument('--mixed-pronunciation',action='store_true',help='Include English Pikoo / pi1-ku1 as an accepted target alongside Mandarin')
    p.add_argument('--phonetic-spelling',action='store_true',help='Constrain pi1-ku1 using exact Chinese homophone text instead of ambiguous Latin spelling')
    a = p.parse_args()
    os.umask(0o077)
    key = None
    for line in a.key_file.read_text().splitlines():
        if line.startswith(('GOOGLE_API_KEY=', 'GEMINI_API_KEY=')):
            key = line.split('=', 1)[1].strip().strip('\"\'')
    if not key:
        raise ValueError('Missing Google API key in private file')
    a.output.mkdir(parents=True, exist_ok=True)
    audio = a.output / 'audio'
    audio.mkdir(exist_ok=True)
    if not 1 <= a.limit <= 96:
        raise ValueError('limit must be between 1 and 96')
    if a.interval < 0:
        raise ValueError('interval must be nonnegative')
    rate_lock = threading.Lock()
    next_request = [0.0]

    def selected_jobs():
        all_rows = jobs(a.mixed_pronunciation,a.phonetic_spelling)
        if a.voices:
            if len(set(a.voices)) != len(a.voices) or any(v not in {r['voice'] for r in all_rows} for v in a.voices):
                raise ValueError('Unknown or duplicate voice')
            voices = a.voices
        else:
            voices = [v for values in VOICES.values() for v in values]
        rows = []
        for voice in voices:
            for label in (1, 0):
                rows.extend([r for r in all_rows if r['voice'] == voice and r['label'] == label][:a.items_per_voice // 2])
        rows = rows[:a.limit]
        for row in rows:
            row['synthetic_style'] = 'childlike' if row['voice'] in a.childlike_voices else 'adult'
            if row['synthetic_style'] == 'childlike':
                row['style'] += (' Use a bright, playful, young-sounding delivery with natural '
                                 'Mandarin child-like timing. This is a fictional synthetic voice.')
        return rows

    def endpoint_payload(voice, content):
        if a.model.startswith('gemini-3.8-'):
            return ('https://generativelanguage.googleapis.com/v1beta/interactions',
                dict(model=a.model, store=False, input=[dict(type='user_input', content=content)],
                     response_format={'type': 'audio'}, generation_config={'speech_config': [{'voice': voice}]}))
        instructions = ('Speak only the exact Chinese utterances below in the order given. '
                        'Leave at least 1.2 seconds of silence between utterances. '
                        'Never read instructions or line numbers. ' + content[0]['annotations'][0]['style'])
        transcript = '\n'.join(c['text'].replace('<long pause>', '') for c in content)
        return ('https://generativelanguage.googleapis.com/v1beta/models/' + a.model + ':generateContent',
            {'contents': [{'parts': [{'text': instructions + '\n\n' + transcript}]}],
             'generationConfig': {'responseModalities': ['AUDIO'],
                 'speechConfig': {'voiceConfig': {'prebuiltVoiceConfig': {'voiceName': voice}}}}})

    def write_wav(path, pcm):
        temporary = path.with_suffix('.partial')
        with wave.open(str(temporary), 'wb') as target:
            target.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            target.writeframes(pcm.tobytes())
        temporary.replace(path)

    def generate_voice(rows):
        # Interleave target and non-target text so file position is not a label cue.
        positives = [r for r in rows if r['label']]
        negatives = [r for r in rows if not r['label']]
        ordered = [row for pair in zip(positives, negatives) for row in pair]
        identity = {'model': a.model, 'rows': ordered, 'kind': 'long-pause-v1'}
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        metadata = audio / (digest[:24] + '.batch.json')
        if metadata.exists():
            cached = json.loads(metadata.read_text())['clips']
            if all(hashlib.sha256((a.output / r['path']).read_bytes()).hexdigest() == r['sha256'] for r in cached):
                return cached
            raise ValueError('Cached batch audio hash mismatch')
        content = [dict(type='text', text=r['text'] + '。<long pause>',
                       annotations=[dict(type='speech_metadata', style=r['style'] +
                        ' Leave at least one second of silence after this utterance.')]) for r in ordered]
        url, payload = endpoint_payload(rows[0]['voice'], content)
        opener = build_opener(ProxyHandler({'http': a.proxy, 'https': a.proxy} if a.proxy else {}))
        request = Request(url,
            data=json.dumps(payload).encode(), headers={'x-goog-api-key': key,
                'Content-Type': 'application/json'}, method='POST')
        delay = next_request[0] - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        next_request[0] = time.monotonic() + a.interval
        try:
            with opener.open(request, timeout=55) as reply:
                response = json.load(reply)
        except HTTPError as error:
            decoded = json.loads(error.read())
            details = decoded.get('error', decoded)
            (a.output / 'last-api-error.json').write_text(json.dumps({
                'code': error.code, 'status': details.get('status'), 'details': details.get('details', []),
                'message': str(details.get('message', '')).replace(key, '[REDACTED]'),
                'safe_error_body':json.loads(json.dumps(decoded).replace(key,'[REDACTED]')),
                'retry_after': error.headers.get('Retry-After')}, indent=2))
            raise RuntimeError(f'Gemini TTS HTTP {error.code}; stop and inspect quota/network') from None
        (audio / (digest[:24] + '.response-meta.json')).write_text(json.dumps({
            'model': a.model, 'voice': rows[0]['voice'], 'status': response.get('status'),
            'usage': response.get('usage', response.get('usageMetadata')),
            'finish_reasons': [c.get('finishReason') for c in response.get('candidates', [])],
            'prompt_feedback': response.get('promptFeedback')}, indent=2))
        pcm = decode_audio(response, max_seconds=90)
        write_wav(audio / (digest[:24] + '.batch.wav'), pcm)
        segments = split_utterances(pcm, len(ordered))
        result = []
        for index, (row, clip) in enumerate(zip(ordered, segments)):
            path = audio / f'{digest[:24]}-{index:02}.wav'
            write_wav(path, clip)
            result.append({**row, 'path': str(path.relative_to(a.output)), 'model': a.model,
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'batch_id': digest,
                'alignment': 'energy-gaps-count-checked; transcript-review-required'})
        metadata.write_text(json.dumps({'request': identity, 'clips': result,
                                       'usage': response.get('usage')}, ensure_ascii=False, indent=2))
        return result

    def generate(row):
        identity = {'model': a.model, **row}
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        path = audio / (digest[:24] + '.wav')
        metadata = audio / (digest[:24] + '.json')
        if not (path.exists() and metadata.exists()):
            url, payload = endpoint_payload(row['voice'], [dict(type='text', text=row['text'],
                    annotations=[dict(type='speech_metadata', style=row['style'])])])
            opener = build_opener(ProxyHandler({'http': a.proxy, 'https': a.proxy} if a.proxy else {}))
            request = Request(url,
                data=json.dumps(payload).encode(), headers={'x-goog-api-key': key,
                    'Content-Type': 'application/json'}, method='POST')
            # Do not rotate projects/models to bypass quota or retry rejected jobs.
            with rate_lock:
                delay = next_request[0] - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                next_request[0] = time.monotonic() + a.interval
            try:
                with opener.open(request, timeout=55) as reply:
                    response = json.load(reply)
            except HTTPError as error:
                try:
                    details = json.loads(error.read()).get('error', {})
                    # Error messages can echo inputs. Only retain status and structured
                    # quota details, never the authenticated request or headers.
                    safe = {'code': error.code, 'status': details.get('status'),
                            'details': details.get('details', [])}
                    (a.output / 'last-api-error.json').write_text(json.dumps(safe, indent=2))
                except (ValueError, OSError):
                    pass
                raise RuntimeError(f'Gemini TTS HTTP {error.code}; stop and inspect quota/network') from None
            pcm = decode_audio(response)
            write_wav(path, pcm)
            metadata.write_text(json.dumps({'request': identity,
                'usage': response.get('usage'), 'created': response.get('created'),
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}, ensure_ascii=False, indent=2))
        saved = json.loads(metadata.read_text())
        if saved['sha256'] != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError('Cached audio hash mismatch')
        return {**row, 'path': str(path.relative_to(a.output)), 'sha256': saved['sha256'],
                'model': a.model}

    completed = []
    rejected = []
    try:
        if a.batch_voices:
            if a.limit % a.items_per_voice:
                raise ValueError('Batch generation requires a complete set of utterances per voice')
            selected = selected_jobs()
            for start in range(0, len(selected), a.items_per_voice):
                batch = selected[start:start + a.items_per_voice]
                try:
                    completed.extend(generate_voice(batch))
                except ValueError as error:
                    # A malformed synthesis is not a reason to weaken alignment or
                    # repeatedly spend quota on the same voice. Skip it explicitly.
                    rejected.append({'voice': batch[0]['voice'], 'reason': str(error)})
                    (a.output / 'rejected-batches.json').write_text(json.dumps(rejected, indent=2))
                    print(json.dumps({'discarded_voice': batch[0]['voice'], 'reason': str(error)}), flush=True)
                (a.output / 'manifest.json').write_text(json.dumps(completed, ensure_ascii=False, indent=2))
                print(json.dumps({'completed': len(completed), 'expected': a.limit,
                                  'batch_voices': True}), flush=True)
            return
        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            selected = selected_jobs()
            for start in range(0, len(selected), a.workers):
                # At most two in flight: a quota failure cannot leave the entire
                # corpus queued for further rejected API calls.
                for row in pool.map(generate, selected[start:start + a.workers]):
                    completed.append(row)
                    (a.output / 'manifest.json').write_text(json.dumps(completed, ensure_ascii=False, indent=2))
                    print(json.dumps({'completed': len(completed), 'expected': min(96, a.limit),
                                      'split': row['split'], 'label': row['label']}), flush=True)
    finally:
        (a.output / 'generation-status.json').write_text(json.dumps({
            'completed_manifest_rows': len(completed), 'expected': min(96, a.limit),
            'model': a.model, 'synthetic_not_human': True,
            'rejected_batches': rejected,
            'finished_unix': int(time.time())}, indent=2))


if __name__ == '__main__':
    main()
