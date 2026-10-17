#!/usr/bin/env python3
"""Import the pinned PolyAI MInDS-14 Chinese subset as training negatives only.

CC-BY-4.0; cite PolyAI and Gerz et al. (2021). The source has no speaker IDs,
so it cannot support a claim of speaker-disjoint validation. No local family
recordings are read. Requires optional pyarrow==19.0.1.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import struct
import wave
import numpy as np
from generate_google import resample

REVISION = '40ce77cb32a384e4d50a568e1ec39ac804019d33'
SOURCE = 'https://huggingface.co/datasets/PolyAI/minds14'


def decode_wave(blob):
    if blob[:4] != b'RIFF' or blob[8:12] != b'WAVE':
        raise ValueError('Expected RIFF WAVE')
    chunks = {}
    offset = 12
    while offset + 8 <= len(blob):
        tag, size = struct.unpack_from('<4sI', blob, offset)
        offset += 8
        if offset + size > len(blob):
            raise ValueError('Truncated WAV chunk')
        chunks[tag] = blob[offset:offset + size]
        offset += size + size % 2
    fmt, channels, rate, _, _, bits = struct.unpack_from('<HHIIHH', chunks[b'fmt '])
    if channels != 1 or rate != 8000:
        raise ValueError('Expected mono 8kHz telephone recording')
    if fmt == 1 and bits == 16:
        return np.frombuffer(chunks[b'data'], '<i2')
    if fmt == 7 and bits == 8:
        codes = np.bitwise_not(np.frombuffer(chunks[b'data'], np.uint8)).astype(np.int32)
        magnitude = (((codes & 15) << 3) + 132) << ((codes >> 4) & 7)
        values = magnitude - 132
        return np.where(codes & 128, -values, values).astype('<i2')
    raise ValueError('Unsupported telephone WAV encoding')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parquet', type=Path, required=True)
    p.add_argument('--sha256', required=True, help='Expected LFS SHA-256 from the pinned source tree')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    os.umask(0o077)
    digest = hashlib.sha256(a.parquet.read_bytes()).hexdigest()
    if digest != a.sha256:
        raise ValueError('Parquet source hash mismatch')
    import pyarrow.parquet as pq
    rows = pq.read_table(a.parquet).to_pylist()
    a.output.mkdir(parents=True, exist_ok=True)
    audio = a.output / 'audio'
    audio.mkdir(exist_ok=True)
    manifest = []
    seen = set()
    excluded = 0
    for row in rows:
        text = row['transcription']
        normalized = re.sub(r'[^\u4e00-\u9fff]', '', text)
        if row['lang_id'] != 13 or any(word in normalized for word in ('你好皮酷', '你好皮裤', '你好皮库')):
            excluded += 1
            continue
        pcm = decode_wave(row['audio']['bytes'])
        if not .3 <= len(pcm) / 8000 <= 60:
            raise ValueError('Invalid source recording duration')
        key = hashlib.sha256(pcm.tobytes()).hexdigest()
        if key in seen:
            excluded += 1
            continue
        seen.add(key)
        path = audio / (key[:24] + '.wav')
        samples = np.clip(np.rint(resample(pcm, 8000)), -32768, 32767).astype('<i2')
        with wave.open(str(path), 'wb') as w:
            w.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            w.writeframes(samples.tobytes())
        manifest.append(dict(path=str(path.relative_to(a.output)), label=0, split='train',
            group='minds14-unknown-speakers-training-only',
            source='PolyAI-MInDS14-zh-CN', text=text, source_path=row['path'],
            source_revision=REVISION, source_license='CC-BY-4.0', source_url=SOURCE,
            original_sample_rate=8000, real_child=False,
            hard_negative='你好' in text, sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    (a.output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    report = dict(source=SOURCE, revision=REVISION, license='CC-BY-4.0',
        attribution='PolyAI; Gerz et al. (2021), Multilingual and Cross-Lingual Intent Detection from Spoken Data',
        parquet_sha256=digest, input_rows=len(rows), imported_training_negatives=len(manifest),
        excluded=excluded, limitations=['No target wake phrase positives',
            'No speaker IDs or child/adult age labels; training only',
            '8kHz telephone-band speech resampled to 16kHz; not wideband microphone audio'])
    (a.output / 'source-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
