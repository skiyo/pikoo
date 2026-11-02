#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Bounded public playback-noise corpus and continuous, fixed-policy scoring.

Never opens household audio or old TEST, generates paid audio, or flashes a
device. ESC source folds are retained; fold 5 stays sealed until explicitly
requested for a frozen candidate. The audio and derived weights stay private.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import time
import urllib.request
import wave

import numpy as np

ESC_COMMIT = '33c8ce9eb2cf0b1c2f8bcf322eb349b6be34dbb6'
ESC_ROOT = f'https://raw.githubusercontent.com/karolpiczak/ESC-50/{ESC_COMMIT}'


def contains_target(text):
    normalized = re.sub(r'[^a-z\u4e00-\u9fff]', '', text.lower())
    return any(prefix+name in normalized
               for prefix in ('hi', '嗨', '海')
               for name in ('pikoo', 'piku', 'piko', 'peekoo', 'peecoo',
                            '皮酷', '皮库', '皮枯', '批枯', '皮扣', '皮科'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fetch(url, path, limit):
    """Atomic bounded CLI download; never prints possibly signed audio URLs."""
    path = Path(path)
    if path.exists():
        if path.stat().st_size > limit:
            raise ValueError('Cached resource exceeds byte limit')
        return
    request = urllib.request.Request(url, headers={'User-Agent': 'Pikoo-negative-research/1'})
    with urllib.request.urlopen(request, timeout=45) as response:
        data = response.read(limit+1)
    if len(data) > limit:
        raise ValueError('Resource exceeds byte limit')
    temp = path.with_suffix(path.suffix+'.partial')
    temp.write_bytes(data)
    temp.replace(path)


def http_json(url):
    # Public metadata only: one bounded transient retry, no paid API retries.
    for attempt in range(2):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                return json.load(response)
        except (OSError, ValueError):
            if attempt:
                raise
            time.sleep(1)


def esc_partition(rows):
    """Source recording isolation is the dataset's official fold contract."""
    result = []
    for category in sorted({r['category'] for r in rows}):
        for split, folds, count in [('train', {'1', '2', '3'}, 6),
                                     ('validation', {'4'}, 2)]:
            candidates = sorted([r for r in rows if r['category'] == category and r['fold'] in folds],
                                key=lambda r: hashlib.sha256(r['filename'].encode()).hexdigest())
            result.extend({**row, 'split': split} for row in candidates[:count])
    sources = {}
    for row in result:
        if sources.setdefault(row['src_file'], row['split']) != row['split']:
            raise ValueError('Source recording crosses partitions')
    return result


def collect(root):
    root.mkdir(parents=True, exist_ok=True)
    raw, audio = root/'original', root/'audio'
    raw.mkdir(exist_ok=True)
    audio.mkdir(exist_ok=True)
    fetch(ESC_ROOT+'/meta/esc50.csv', root/'esc50.csv', 300000)
    fetch(ESC_ROOT+'/README.md', root/'ESC-README.md', 200000)
    rows = esc_partition(list(csv.DictReader(io.StringIO((root/'esc50.csv').read_text()))))

    def download(row):
        path = raw/row['filename']
        fetch(ESC_ROOT+'/audio/'+row['filename'], path, 450000)
        return row, path

    manifest = []
    # ffmpeg is an existing local dependency; no Python audio decoder download.
    with ThreadPoolExecutor(max_workers=4) as pool:
        for n, (row, original) in enumerate(pool.map(download, rows), 1):
            path = audio/row['filename']
            if not path.exists():
                subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(original),
                    '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', str(path)], check=True)
            manifest.append({'path': str(path.relative_to(root)), 'sha256': sha(path),
                'original_sha256': sha(original), 'source': 'ESC-50', 'source_commit': ESC_COMMIT,
                'source_recording': row['src_file'], 'fold': int(row['fold']),
                'category': row['category'], 'split': row['split'], 'label': 0,
                'license': 'CC-BY-3.0' if row['esc10'] == 'True' else 'CC-BY-NC-3.0',
                'license_scope': 'Original dataset terms; private research only; not Apache-2.0',
                'synthetic': False, 'household': False,
                'label_basis': 'Official non-speech environmental category; not filename keyword inference'})
            if n % 50 == 0:
                print(json.dumps({'downloaded_and_converted': n, 'total': len(rows)}), flush=True)
    (root/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    report = {'status': 'public-negative-corpus-collected', 'clips': len(manifest),
        'categories': len({r['category'] for r in manifest}),
        'train': sum(r['split'] == 'train' for r in manifest),
        'validation': sum(r['split'] == 'validation' for r in manifest),
        'original_download_bytes': sum(p.stat().st_size for p in raw.iterdir()),
        'sealed_fold_5_opened': False, 'family_audio_used': False, 'paid_api_requests': 0}
    (root/'collection-report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report), flush=True)


def load_rows(manifest, protected):
    protected = set(json.loads(protected.read_text())['audio_sha256'].values())
    rows = json.loads(manifest.read_text())
    sources, hashes, speakers = {}, {}, {}
    for row in rows:
        if row.get('source') not in {'ESC-50', 'ChildMandarin', 'LibriSpeech-train.100', 'public-speech-playlist'}:
            raise ValueError('Unsupported public corpus source')
        if row['split'] not in ('train', 'validation') or row['label'] != 0:
            raise ValueError('Only explicit TRAIN/DEV negatives allowed')
        if row.get('household') is not False or row.get('evaluation_only') or row.get('frozen_holdout'):
            raise ValueError('Protected recording metadata')
        if row['sha256'] in protected or row.get('original_sha256') in protected or set(row.get('parent_sha256s', [])) & protected:
            raise ValueError('Protected waveform')
        path = (manifest.parent/row['path']).resolve()
        if not path.is_relative_to(manifest.parent.resolve()) or sha(path) != row['sha256']:
            raise ValueError('Negative corpus hash/path mismatch')
        source = (row['source'], row['source_recording'])
        if sources.setdefault(source, row['split']) != row['split']:
            raise ValueError('Source leakage')
        if hashes.setdefault(row['sha256'], row['split']) != row['split']:
            raise ValueError('Waveform leakage')
        for speaker in ([row['speaker']] if row.get('speaker') else [])+row.get('parent_speakers', []):
            if speakers.setdefault(speaker, row['split']) != row['split']:
                raise ValueError('Speaker leakage')
        for parent in row.get('parent_sha256s', []):
            if hashes.setdefault(parent, row['split']) != row['split']:
                raise ValueError('Derived recording leakage')
    return rows


def read_pcm(path):
    with wave.open(str(path)) as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, 16000):
            raise ValueError('Expected mono 16kHz PCM16')
        return np.frombuffer(w.readframes(w.getnframes()), '<i2')


def collect_speech(root, child_manifest, child_dev_archive, protected_file):
    """Reuse licensed Chinese child TRAIN; add disjoint public speech DEV.

    LibriSpeech uses only official train.100 sources with speaker partitioning.
    ChildMandarin uses official TRAIN/DEV, never test.tar. Its terms stay private.
    No household audio is read. Signed download URLs are not persisted or logged.
    """
    from collections import defaultdict
    from import_childmandarin import inventory
    protected = set(json.loads(protected_file.read_text())['audio_sha256'].values())
    output = root/'speech'
    output.mkdir(parents=True, exist_ok=True)
    audio = output/'audio'
    audio.mkdir(exist_ok=True)
    manifest = []
    used, speakers = set(), {}

    def child_row(data, speaker, split, text, age, original_hash=None):
        if contains_target(text):
            return
        digest = hashlib.sha256(data).hexdigest()
        if digest in protected or digest in used:
            return
        if speakers.setdefault(speaker, split) != split:
            raise ValueError('Chinese child speaker crosses official partitions')
        path = audio/(digest+'.wav')
        path.write_bytes(data)
        used.add(digest)
        manifest.append({'path': str(path.relative_to(output)), 'sha256': digest,
            'original_sha256': original_hash or digest, 'source': 'ChildMandarin',
            'source_recording': digest, 'speaker': speaker, 'split': split, 'label': 0,
            'category': 'Chinese-child-ordinary-speech', 'real_child': True, 'age': age,
            'license': 'CC-BY-NC-SA-4.0 plus dataset access terms; private only',
            'household': False, 'synthetic': False, 'original_full_utterance': True,
            'transcript_sha256': hashlib.sha256(text.encode()).hexdigest(),
            'label_basis': 'Official ordinary-speech transcript; target/homophones excluded'})

    grouped = defaultdict(list)
    for row in json.loads(child_manifest.read_text()):
        if row['source'] != 'ChildMandarin' or row['split'] != 'train' or row['label'] != 0:
            continue
        if not row.get('original_full_utterance') or row['sha256'] in protected:
            continue
        grouped[row['speaker']].append(row)
    for speaker, rows in sorted(grouped.items()):
        rows = sorted(rows, key=lambda r: hashlib.sha256(('negative-refresh:'+r['sha256']).encode()).hexdigest())
        for row in rows[:2]:
            path = child_manifest.parent/row['path']
            if sha(path) != row['sha256']:
                raise ValueError('Child TRAIN integrity mismatch')
            child_row(path.read_bytes(), speaker, 'train', row.get('text', ''), row['age'])
    # Official DEV is reused development, explicitly never independent TEST.
    with tarfile.open(child_dev_archive, 'r:*') as archive:
        rows, _ = inventory(archive, 'validation', skip_missing_audio=True)
        grouped = defaultdict(list)
        for row in rows:
            grouped[row['speaker']].append(row)
        for speaker, rows in sorted(grouped.items()):
            speaker = 'ChildMandarin:'+hashlib.sha256(('ChildMandarin:'+speaker).encode()).hexdigest()[:16]
            count = 0
            for row in sorted(rows, key=lambda r: hashlib.sha256(r['member'].name.encode()).hexdigest()):
                with archive.extractfile(row['member']) as f:
                    data = f.read()
                before = len(manifest)
                child_row(data, speaker, 'validation', row['text'], row['age'])
                count += len(manifest)>before
                if count >= 3:
                    break
    print(json.dumps({'speech_collected': len(manifest), 'source': 'licensed existing Chinese child audio'}), flush=True)

    # 15 spaced source regions, eight recordings each; ~tens of MB, not the
    # multi-GB corpus. No requests to paid voice models.
    for offset in range(0, 28001, 2000):
        url = ('https://datasets-server.huggingface.co/rows?dataset=openslr%2Flibrispeech_asr'
               f'&config=clean&split=train.100&offset={offset}&length=8')
        payload = http_json(url)
        for item in payload['rows']:
            row = item['row']
            text = row['text'].lower()
            if contains_target(text) or any(word in text for word in ('pikoo', 'piko', 'piku', 'pee koo', 'peeko')):
                continue
            speaker = 'LibriSpeech:'+str(row['speaker_id'])
            split = 'validation' if int(hashlib.sha256(speaker.encode()).hexdigest()[:8], 16)%4 == 0 else 'train'
            if speakers.setdefault(speaker, split) != split:
                raise ValueError('English speaker split drift')
            name = hashlib.sha256(row['id'].encode()).hexdigest()
            original, path = audio/(name+'.flac'), audio/(name+'.wav')
            fetch(row['audio'][0]['src'], original, 3000000)
            if not path.exists():
                subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(original),
                    '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', str(path)], check=True)
            if sha(path) in protected:
                raise ValueError('Protected English recording')
            manifest.append({'path': str(path.relative_to(output)), 'sha256': sha(path),
                'original_sha256': sha(original), 'source': 'LibriSpeech-train.100',
                'source_recording': row['id'], 'speaker': speaker, 'split': split, 'label': 0,
                'category': 'English-adult-ordinary-speech', 'license': 'CC-BY-4.0',
                'household': False, 'synthetic': False, 'text': row['text'],
                'label_basis': 'Published transcript with target-name exclusion'})
        print(json.dumps({'English_source_offset': offset, 'speech_recordings': len(manifest)}), flush=True)
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    combined = [{**r, 'path': str(Path('speech')/r['path'])} for r in manifest]
    combined += json.loads((root/'manifest.json').read_text())
    (root/'combined-manifest.json').write_text(json.dumps(combined, indent=2)+'\n')
    # Also check speaker, not merely recording, isolation before any scoring.
    by_speaker = {}
    for row in combined:
        key = row.get('speaker')
        if key and by_speaker.setdefault(key, row['split']) != row['split']:
            raise ValueError('Speaker leakage')
    load_rows(root/'combined-manifest.json', protected_file)
    print(json.dumps({'status': 'speech-and-environment-negatives-ready', 'clips': len(combined),
        'speech_clips': len(manifest), 'household_used': False, 'TEST_opened': False}), flush=True)


def native_probabilities(model, features, micro, scratch):
    from streaming_runtime import interpreter, quantize
    engine = interpreter(model)
    engine.allocate_tensors()
    inp, out = engine.get_input_details()[0], engine.get_output_details()[0]
    if list(inp['shape']) != [1, 3, 40] or inp['dtype'] != np.int8 or out['dtype'] != np.uint8 or int(np.prod(out['shape'])) != 1:
        raise ValueError('Unexpected installed-model streaming contract')
    n = len(features)//3
    fixture, trace = scratch/'features.int8', scratch/'trace.uint8'
    fixture.write_bytes(quantize(features[:n*3], *inp['quantization']).tobytes())
    result = subprocess.run([str(micro), str(model), str(fixture), '--trace-output', str(trace)],
                            capture_output=True, text=True, check=True)
    proof = json.loads(result.stdout.strip().splitlines()[-1])
    raw = np.frombuffer(trace.read_bytes(), np.uint8).reshape(3, n)
    if not np.array_equal(raw, np.tile(raw[0], (3, 1))):
        raise ValueError('Native reset consistency failure')
    scale, zero = out['quantization']
    return (raw[0].astype(float)-zero)*scale, proof['host_arena_used_bytes']


def playlists(manifest, protected):
    rows = load_rows(manifest, protected)
    target = manifest.parent/'playlists'
    target.mkdir(exist_ok=True)
    result = list(rows)
    for split in ('train', 'validation'):
        for category in ('Chinese-child-ordinary-speech', 'English-adult-ordinary-speech'):
            part = sorted([r for r in rows if r['split'] == split and r['category'] == category],
                          key=lambda r: r['sha256'])
            # Separate finite playlists exercise state across source boundaries.
            count = 4 if split == 'train' else 2
            for index in range(count):
                selected, samples = [], []
                for row in part[index::count]:
                    samples.append(read_pcm(manifest.parent/row['path']))
                    samples.append(np.zeros(2400, dtype='<i2'))
                    selected.append(row)
                    if sum(len(s) for s in samples) >= 60*16000:
                        break
                if not selected:
                    continue
                name = f'{split}-{category}-{index}.wav'
                path = target/name
                with wave.open(str(path), 'wb') as w:
                    w.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
                    w.writeframes(np.concatenate(samples).astype('<i2').tobytes())
                result.append({'path': str(path.relative_to(manifest.parent)), 'sha256': sha(path),
                    'original_sha256': sha(path), 'source': 'public-speech-playlist',
                    'source_recording': name, 'split': split, 'label': 0,
                    'category': category+'-continuous-playlist', 'synthetic': False,
                    'household': False, 'derived': True,
                    'license': 'All parent restrictions apply; private research only',
                    'parent_sha256s': [r['sha256'] for r in selected],
                    'parent_speakers': sorted({r['speaker'] for r in selected}),
                    'label_basis': 'Same-partition ordinary speech concatenated with 150ms gaps; not actual TV'})
    output = manifest.parent/'playback-manifest.json'
    output.write_text(json.dumps(result, indent=2)+'\n')
    load_rows(output, protected)
    print(json.dumps({'status': 'continuous-playlists-added', 'playlists': len(result)-len(rows),
                      'total': len(result), 'test_opened': False}), flush=True)


def expand_english(manifest, protected):
    """Add new public TRAIN speech; keep the entire current DEV unchanged."""
    rows = load_rows(manifest, protected)
    known = {r['source_recording'] for r in rows if r['source'] == 'LibriSpeech-train.100'}
    root = manifest.parent
    audio = root/'extra-english'
    audio.mkdir(exist_ok=True)
    extra = []
    for offset in range(500, 28000, 1000):
        payload = http_json('https://datasets-server.huggingface.co/rows?dataset=openslr%2Flibrispeech_asr'
                            f'&config=clean&split=train.100&offset={offset}&length=8')
        for item in payload['rows']:
            row = item['row']
            speaker = 'LibriSpeech:'+str(row['speaker_id'])
            if int(hashlib.sha256(speaker.encode()).hexdigest()[:8], 16)%4 == 0:
                continue  # DEV speakers never become training or mining inputs.
            if row['id'] in known or contains_target(row['text']):
                continue
            name = hashlib.sha256(row['id'].encode()).hexdigest()
            original, path = audio/(name+'.flac'), audio/(name+'.wav')
            fetch(row['audio'][0]['src'], original, 3000000)
            if not path.exists():
                subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(original),
                    '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', str(path)], check=True)
            extra.append({'path': str(path.relative_to(root)), 'sha256': sha(path),
                'original_sha256': sha(original), 'source': 'LibriSpeech-train.100',
                'source_recording': row['id'], 'speaker': speaker, 'split': 'train', 'label': 0,
                'category': 'English-adult-ordinary-speech', 'license': 'CC-BY-4.0',
                'household': False, 'synthetic': False, 'text': row['text'],
                'label_basis': 'Published ordinary-speech transcript; no DEV-targeted text generation'})
            known.add(row['id'])
        print(json.dumps({'extra_english_train': len(extra), 'source_offset': offset}), flush=True)
    output = root/'expanded-manifest.json'
    output.write_text(json.dumps(rows+extra, indent=2)+'\n')
    load_rows(output, protected)
    print(json.dumps({'added_English_TRAIN': len(extra), 'DEV_unchanged': True}), flush=True)


def verify_dev(model, cache, cases_path, protected_file, micro, output):
    """Full existing wake DEV, exact native/reference agreement and resets."""
    from hi_pikoo_model import policy_metrics
    protected = set(json.loads(protected_file.read_text())['audio_sha256'].values())
    cases = json.loads(cases_path.read_text())
    if any(c['sha256'] in protected for c in cases):
        raise ValueError('Protected DEV case')
    with np.load(cache) as data:
        features = data['dev_x']
    if len(features) != len(cases):
        raise ValueError('Incomplete DEV')
    output.mkdir(parents=True, exist_ok=False)
    arena = 0
    native_cases = []
    with tempfile.TemporaryDirectory(dir=output) as temporary:
        for data, case in zip(features, cases):
            probs, used = native_probabilities(model, data[:case['valid_steps']*3], micro, Path(temporary))
            if not np.array_equal(probs, np.asarray(case['probabilities'])):
                raise ValueError('Full DEV native/reference output differs')
            arena = max(arena, used)
            native_cases.append({**case, 'probabilities': probs.tolist()})
    proof = {'status': 'passed-full-wake-DEV-native-parity', 'cases': len(cases),
        'model_sha256': sha(model), 'features_sha256': sha(cache),
        'reference_cases_sha256': sha(cases_path), 'micro_sha256': sha(micro),
        'reset_rounds': 3, 'byte_exact': True, 'host_arena_bytes': arena,
        'fixed_policy': policy_metrics(native_cases, 3, .9),
        'household_used': False, 'test_opened': False, 'ESP32_hardware_accepted': False}
    (output/'proof.json').write_text(json.dumps(proof, indent=2)+'\n')
    print(json.dumps(proof), flush=True)


def metrics(probabilities, threshold=.9, rolling=3, cooldown_ms=3000):
    from hi_pikoo_model import event_scores
    scores = event_scores(probabilities, rolling)
    fired, last = [], -1e9
    for i in np.flatnonzero(scores >= threshold):
        if i*30-last >= cooldown_ms:
            fired.append(int(i)*30)
            last = i*30
    return {'peak': float(max(scores, default=0)), 'false_events_3s_cooldown': len(fired),
            'first_false_ms': fired[0] if fired else None}


def score(manifest, protected, model, micro, output):
    from hi_pikoo_train import features_and_times
    manifest_hash, model_hash, micro_hash = sha(manifest), sha(model), sha(micro)
    rows = load_rows(manifest, protected)
    output.mkdir(parents=True, exist_ok=False)
    cases = []
    with tempfile.TemporaryDirectory(dir=output) as temp:
        for n, row in enumerate(rows, 1):
            pcm = read_pcm(manifest.parent/row['path'])
            # One continuous original, frontend/model reset only at recording
            # boundaries, never at the arbitrary four-second training crops.
            features, _ = features_and_times(np.pad(pcm, (16000, 16000)))
            probs, arena = native_probabilities(model, features, micro, Path(temp))
            cases.append({**row, **metrics(probs), 'audio_seconds': len(pcm)/16000,
                          'native_arena_bytes': arena})
            if n % 50 == 0:
                print(json.dumps({'scored': n, 'total': len(rows),
                    'false_clips': sum(c['false_events_3s_cooldown'] > 0 for c in cases)}), flush=True)
    summary = {}
    for split in ('train', 'validation'):
        part = [c for c in cases if c['split'] == split]
        seconds = sum(c['audio_seconds'] for c in part)
        summary[split] = {'clips': len(part), 'seconds': seconds,
            'false_clips': sum(c['false_events_3s_cooldown'] > 0 for c in part),
            'false_events_3s_cooldown': sum(c['false_events_3s_cooldown'] for c in part)}
    if (sha(manifest), sha(model), sha(micro)) != (manifest_hash, model_hash, micro_hash):
        raise ValueError('Inputs changed while scoring')
    report = {'model_sha256': model_hash, 'manifest_sha256': manifest_hash, 'micro_sha256': micro_hash,
        'rolling': 3, 'threshold': .9, 'backend': 'pinned native TFLite Micro',
        'summary': summary, 'cases': cases, 'household_used': False,
        'sealed_test_opened': False, 'scope': 'TRAIN mining / DEV model selection, not independent acceptance'}
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(summary), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    c = sub.add_parser('collect')
    c.add_argument('--output', type=Path, required=True)
    sp = sub.add_parser('collect-speech')
    for flag in ('root', 'child-manifest', 'child-dev-archive', 'protected-hashes'):
        sp.add_argument('--'+flag, type=Path, required=True)
    pl = sub.add_parser('playlists')
    for flag in ('manifest', 'protected-hashes'):
        pl.add_argument('--'+flag, type=Path, required=True)
    ex = sub.add_parser('expand-english')
    for flag in ('manifest', 'protected-hashes'):
        ex.add_argument('--'+flag, type=Path, required=True)
    ve = sub.add_parser('verify-dev')
    for flag in ('model', 'cache', 'cases', 'protected-hashes', 'micro', 'output'):
        ve.add_argument('--'+flag, type=Path, required=True)
    s = sub.add_parser('score')
    for flag in ('manifest', 'protected-hashes', 'model', 'micro', 'output'):
        s.add_argument('--'+flag, type=Path, required=True)
    a = p.parse_args()
    os.umask(0o077)
    if a.command == 'collect':
        collect(a.output)
    elif a.command == 'collect-speech':
        collect_speech(a.root, a.child_manifest, a.child_dev_archive, a.protected_hashes)
    elif a.command == 'playlists':
        playlists(a.manifest, a.protected_hashes)
    elif a.command == 'expand-english':
        expand_english(a.manifest, a.protected_hashes)
    elif a.command == 'verify-dev':
        verify_dev(a.model, a.cache, a.cases, a.protected_hashes, a.micro.resolve(), a.output)
    else:
        score(a.manifest, a.protected_hashes, a.model, a.micro.resolve(), a.output)


if __name__ == '__main__':
    main()
