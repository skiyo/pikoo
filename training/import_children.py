#!/usr/bin/env python3
"""Import authorized local Mandarin child WAVs; never download gated corpora.
A reviewed CSV maps each relative WAV path to speaker, age, split, text, label,
recording_session. Keep this CSV, recordings, manifests and derived models private.
"""
import argparse, csv, hashlib, json, os, wave
from pathlib import Path

SPLITS = {'train', 'validation', 'test'}
WAKE_HOMOPHONES = ('你好皮酷', '你好皮裤', '你好皮库')

def import_data(root, index, output, source, rights):
    root, output = root.resolve(), output.resolve()
    if not rights.is_file():
        raise ValueError('Provide a local record of permission/license before importing')
    with index.open(encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    speakers, recordings, hashes, result = {}, {}, {}, []
    # Validate the entire index before writing any audio.
    prepared = []
    for row in rows:
        path = (root / row['path']).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Audio must be a regular file inside the authorized data root')
        speaker, split = row['speaker'].strip(), row['split']
        age, label = float(row['age']), int(row['label'])
        if not speaker or split not in SPLITS or not 2 <= age < 18 or label not in (0, 1):
            raise ValueError('Invalid child metadata or split')
        if row.get('language') != 'zh-CN':
            raise ValueError('This importer requires verified Mandarin speech, language=zh-CN')
        group = row['recording_session'].strip()
        if not group:
            raise ValueError('Recording session is required')
        for mapping, key in [(speakers, speaker), (recordings, speaker + ':' + group)]:
            if key in mapping and mapping[key] != split:
                raise ValueError('Speaker/session leakage across splits')
            mapping[key] = split
        text = ''.join(row['text'].split())
        if label == 0 and any(word in text for word in WAKE_HOMOPHONES):
            raise ValueError('Wake phrase or homophone cannot be labeled negative')
        if label == 1 and text != '你好皮酷':
            raise ValueError('Positive clips must contain the reviewed exact wake phrase')
        with wave.open(str(path)) as wav:
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, 16000):
                raise ValueError('Convert to mono PCM16/16kHz first; retain original privately')
            if not .3 <= wav.getnframes() / 16000 <= 30:
                raise ValueError('Use reviewed utterance clips between 0.3 and 30 seconds')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in hashes:
            if hashes[digest] != split: raise ValueError('Duplicate audio across splits')
            continue
        hashes[digest] = split
        # Pseudonymous IDs; no child's name in training reports.
        anonymous = hashlib.sha256((source + ':' + speaker).encode()).hexdigest()[:16]
        prepared.append((path, digest, {'path': 'audio/' + digest + '.wav', 'label': label,
            'text': row['text'], 'speaker': source + ':' + anonymous, 'group': source + ':' + anonymous,
            'recording_session': hashlib.sha256(group.encode()).hexdigest()[:16],
            'split': split, 'age': age, 'language': 'zh-CN', 'source': source,
            'real_child': True, 'sha256': digest, 'restricted': True}))
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    (output / 'audio').mkdir(exist_ok=True, mode=0o700)
    for path, digest, row in prepared:
        dest = output / row['path']; dest.write_bytes(path.read_bytes()); dest.chmod(0o600)
        result.append(row)
    (output / 'manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    (output / 'provenance.json').write_text(json.dumps({'source': source,
        'permission_record_sha256': hashlib.sha256(rights.read_bytes()).hexdigest(),
        'real_child_clips': len(result), 'speakers': len(speakers),
        'publication': 'private; review corpus terms before sharing derived models'}, indent=2) + '\n')
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--index',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--source',required=True);p.add_argument('--permission-record',type=Path,required=True)
    a=p.parse_args();os.umask(0o077)
    print('Imported clips:',len(import_data(a.root,a.index,a.output,a.source,a.permission_record)))
if __name__=='__main__':main()
