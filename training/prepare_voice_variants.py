#!/usr/bin/env python3
"""Population-level pitch/tempo augmentation, never real child target speech.

Only derives audio from hash-checked development TTS, preserving the original
speaker split. No voice cloning and no household audio. FFmpeg processes local
PCM; the resulting manifest remains private together with the source corpus.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import wave


PROFILES = [(2., .9), (4., 1.), (6., 1.15), (8., 1.), (5., .8)]
ALLOWED_SOURCES = {'Google-Gemini-TTS-synthetic','Qwen3-TTS-synthetic-local','Google-TTS-level-tone-synthetic'}


def validate_profiles(profiles, fast_speech=False):
    maximum_tempo = 2. if fast_speech else 1.25
    if len(profiles)>5 or any(not math.isfinite(s) or not math.isfinite(t) or not -2<=s<=8 or not .75<=t<=maximum_tempo for s,t in profiles):
        raise ValueError(f'Use at most five finite profiles: -2..8 semitones and 0.75..{maximum_tempo} tempo')


def validate(rows, root, protected, training_only=False):
    groups, hashes = {}, {}
    for row in rows:
        if row.get('evaluation_only') or row.get('frozen_holdout') or str(row.get('source', '')).startswith('private-'):
            raise ValueError('Household/evaluation audio cannot enter development')
        if training_only and row['split'] != 'train':
            raise ValueError('Fast speech derivatives require TRAIN-only input')
        if row['split'] not in ('train', 'validation'):
            raise ValueError('Test recordings cannot enter development')
        path = (root / row['path']).resolve()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in protected:
            raise ValueError('Protected human recording cannot enter development')
        if digest != row.get('sha256'):
            raise ValueError('Missing or mismatched source audio hash')
        group = row.get('speaker', row.get('voice', row.get('group')))
        if not group:
            raise ValueError('Missing source speaker group')
        if group in groups and groups[group] != row['split']:
            raise ValueError('Source speaker crosses splits')
        if digest in hashes and hashes[digest] != row['split']:
            raise ValueError('Source waveform crosses splits')
        groups[group], hashes[digest] = row['split'], row['split']


def transform(ffmpeg, source, destination, semitones, tempo):
    # Resampling changes pitch and the spectral envelope together; time scaling
    # then independently controls duration. This is not a biological child model.
    with wave.open(str(source)) as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 16000):
            raise ValueError('Expected source mono PCM16/16kHz')
    ratio = 2 ** (semitones / 12)
    subprocess.run([ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
        '-i', str(source), '-af',
        f'asetrate={round(16000 * ratio)},aresample=16000,atempo={tempo / ratio:.9f}',
        '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', str(destination)],
        check=True, capture_output=True, timeout=20)
    with wave.open(str(destination)) as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 16000):
            raise ValueError('Unexpected transformed PCM format')
        if not .25 <= audio.getnframes() / 16000 <= 15:
            raise ValueError('Unexpected transformed duration')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--protected-hashes', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--sources',nargs='+',choices=sorted(ALLOWED_SOURCES),default=['Google-Gemini-TTS-synthetic'])
    parser.add_argument('--profile',type=float,nargs=2,action='append',metavar=('SEMITONES','TEMPO'),help='Optional bounded profiles; default is the historical five-profile set')
    parser.add_argument('--fast-speech',action='store_true',help='Explicitly allow tempo up to 2.0 on TRAIN-only input; never changes development audio')
    args = parser.parse_args()
    profiles=args.profile or PROFILES
    validate_profiles(profiles,args.fast_speech)
    os.umask(0o077)
    rows = json.loads(args.manifest.read_text())
    protected = set(json.loads(args.protected_hashes.read_text())['audio_sha256'].values())
    validate(rows, args.manifest.parent, protected,training_only=args.fast_speech)
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise RuntimeError('FFmpeg is required for explicit offline voice augmentation')
    args.output.mkdir(parents=True, exist_ok=True)
    audio_dir = args.output / 'audio'
    audio_dir.mkdir(exist_ok=True)
    original, variants = [], []
    for row in rows:
        source = (args.manifest.parent / row['path']).resolve()
        original.append({**row, 'path': os.path.relpath(source, args.output.resolve())})
        if row.get('source') not in args.sources:
            continue
        if not row.get('synthetic') or row.get('real_child'):
            raise ValueError('Only explicit synthetic TTS is eligible for pitch variants')
        # Absolute wake boundaries would no longer align after tempo changes.
        if 'wake_end_sample' in row:
            raise ValueError('Timestamped source requires explicit boundary remapping')
        for semitones, tempo in profiles:
            identity = {'parent_sha256': row['sha256'], 'semitones': semitones,
                        'tempo': tempo, 'processor': 'ffmpeg-asetrate-atempo-v1'}
            name = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
            output = audio_dir / f'{name}.wav'
            transform(ffmpeg, source, output, semitones, tempo)
            variants.append({**row, 'path': str(output.relative_to(args.output)),
                'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                'source': 'pitch-tempo-augmented-'+{'Google-Gemini-TTS-synthetic':'Google-TTS','Qwen3-TTS-synthetic-local':'Qwen3-TTS','Google-TTS-level-tone-synthetic':'Google-level-tone'}[row['source']], 'synthetic': True,
                'real_child': False, 'augmentation': identity,
                'label_scope': 'synthetic surrogate, not real child target speech'})
    combined = original + variants
    validate(combined, args.output, protected,training_only=args.fast_speech)
    (args.output / 'manifest.json').write_text(json.dumps(combined, ensure_ascii=False, indent=2) + '\n')
    (args.output / 'variants-only.json').write_text(json.dumps(variants, ensure_ascii=False, indent=2) + '\n')
    report = {'status': 'synthetic-development-augmentation-not-child-acceptance',
        'source_manifest_sha256': hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        'ffmpeg_version': subprocess.check_output([ffmpeg, '-version'], text=True).splitlines()[0],
        'profiles': profiles, 'protected_hashes': len(protected),
        'fast_speech_train_only':args.fast_speech,
        'counts': dict(Counter(f"{r['split']}:label={r['label']}" for r in variants)),
        'real_child_positive_recordings': 0, 'household_recordings_used': 0}
    (args.output / 'preparation-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
