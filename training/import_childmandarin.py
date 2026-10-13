#!/usr/bin/env python3
"""Import a speaker-balanced subset of authorized ChildMandarin tar archives.

Never extracts archive paths directly. Original splits and JSON speaker metadata
are authoritative; recordings, indices and models must remain private.
"""
import argparse
import csv
import hashlib
import json
import os
import tarfile
import tempfile
import wave
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

from import_children import import_data, WAKE_HOMOPHONES


def inventory(archive, split):
    members = {}
    for member in archive.getmembers():
        path = PurePosixPath(member.name)
        if path.is_absolute() or '..' in path.parts or member.issym() or member.islnk():
            raise ValueError('Unsafe archive member')
        if not member.isfile():
            continue
        if member.name in members:
            raise ValueError('Duplicate archive path')
        members[member.name] = member
    rows, excluded = [], Counter()
    for name, member in sorted(members.items()):
        if not name.endswith('.json'):
            continue
        if member.size > 65536:
            raise ValueError('Oversized annotation')
        with archive.extractfile(member) as f:
            annotation = json.load(f)
        speaker = str(annotation['speaker_id']).strip()
        age = float(annotation['age'])
        if not speaker or not 3 <= age <= 5:
            raise ValueError('Unexpected ChildMandarin speaker metadata')
        text = ''.join(annotation['text'].split())
        if any(phrase in text for phrase in WAKE_HOMOPHONES):
            excluded['wake_phrase_or_homophone'] += 1
            continue
        audio_name = name[:-5] + '.wav'
        if audio_name not in members:
            raise ValueError('Annotation has no matching WAV')
        wav_member = members[audio_name]
        if not 44 <= wav_member.size <= 2_000_000:
            excluded['audio_size'] += 1
            continue
        # Validate headers before sampling; no transcript or original ID is logged.
        with archive.extractfile(wav_member) as f, wave.open(f) as w:
            if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, 16000):
                raise ValueError('Expected mono PCM16/16kHz')
            seconds = w.getnframes() / 16000
        if not .3 <= seconds <= 30:
            excluded['duration'] += 1
            continue
        rows.append(dict(member=wav_member, speaker=speaker, age=age,
                         text=annotation['text'], split=split, duration=seconds))
    return rows, dict(excluded)


def import_archives(root, output, rights, train_limit=20, eval_limit=10):
    if train_limit < 1 or eval_limit < 1:
        raise ValueError('Sample limits must be positive')
    if not rights.is_file():
        raise ValueError('Permission record required')
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    summary, index_rows, speaker_splits = {}, [], {}
    with tempfile.TemporaryDirectory(prefix='childmandarin-', dir=output) as temporary:
        staging = Path(temporary)
        for filename, split in [('train.tar', 'train'), ('dev.tar', 'validation'), ('test.tar', 'test')]:
            source = root / filename
            with tarfile.open(source, 'r:*') as archive:
                rows, excluded = inventory(archive, split)
                groups = defaultdict(list)
                for row in rows:
                    speaker = row['speaker']
                    if speaker in speaker_splits and speaker_splits[speaker] != split:
                        raise ValueError('Official speaker leaks across splits')
                    speaker_splits[speaker] = split
                    groups[speaker].append(row)
                selected = []
                for speaker in sorted(groups):
                    # Fixed hash ordering is reproducible and independent of model scores.
                    ordered = sorted(groups[speaker], key=lambda r: hashlib.sha256(
                        ('pikoo-child-v1:' + r['member'].name).encode()).hexdigest())
                    selected.extend(ordered[:train_limit if split == 'train' else eval_limit])
                for row in selected:
                    with archive.extractfile(row['member']) as f:
                        data = f.read()
                    path = hashlib.sha256(data).hexdigest() + '.wav'
                    (staging / path).write_bytes(data)
                    index_rows.append(dict(path=path, speaker=row['speaker'], age=row['age'],
                        language='zh-CN', recording_session='official-speaker-group', split=split,
                        label=0, text=row['text']))
                summary[split] = dict(eligible_clips=len(rows), speakers=len(groups),
                    selected_clips=len(selected), selected_seconds=sum(r['duration'] for r in selected),
                    selected_age_counts=dict(Counter(str(r['age']) for r in selected)), excluded=excluded)
            with source.open('rb') as f:
                digest = hashlib.sha256()
                for chunk in iter(lambda: f.read(1024 * 1024), b''):
                    digest.update(chunk)
                summary[split]['archive_sha256'] = digest.hexdigest()
        index = staging / 'index.csv'
        with index.open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['path','speaker','age','language','recording_session','split','label','text'])
            writer.writeheader(); writer.writerows(index_rows)
        imported = import_data(staging, index, output, 'ChildMandarin', rights)
    report = dict(source='BAAI/ChildMandarin', revision='67a5579247989e071911b2e8d72952c2afd43ca3',
        restricted=True, usage='Local noncommercial research; do not redistribute recordings or derivatives',
        purpose='Real Mandarin child speech NEGATIVES; no child wake-word recall claim',
        unique_imported_clips=len(imported), splits=summary)
    (output / 'import-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--archives', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--permission-record', type=Path, required=True)
    p.add_argument('--train-per-speaker', type=int, default=20)
    p.add_argument('--eval-per-speaker', type=int, default=10)
    a = p.parse_args(); os.umask(0o077)
    print(json.dumps(import_archives(a.archives, a.output, a.permission_record,
        a.train_per_speaker, a.eval_per_speaker), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
