#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Extract one opt-in four-second USB capture from an existing private log.

Offline only: never opens USB, enables a microphone, uploads or scores audio.
The log must include idle status before and after exactly one bounded capture.
Extraction proves transport integrity, not consent, freshness or target content.
"""
import argparse
import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
import re
import wave

ANSI = re.compile(r'\x1b\[[0-9;]*m')
FIELDS = ('state', 'muted', 'upload', 'uploaded_samples', 'frames',
          'reconnects', 'uptime_ms', 'wake_errors', 'wake_dropped')
FIXED = ('uploaded_samples', 'frames', 'reconnects', 'wake_errors', 'wake_dropped')


def status(line):
    if 'diag: board=' not in line:
        return None
    fields = dict(re.findall(r'(\w+)=([^\s]+)', line))
    try:
        return {key: int(fields[key]) for key in FIELDS}
    except (KeyError, ValueError) as error:
        raise ValueError('Complete idle/upload/error diagnostics required') from error


def decode_capture(raw):
    """Reject truncated, interleaved, duplicate, reset or uploading captures."""
    lines = ANSI.sub('', raw.decode('utf-8', errors='strict')).splitlines()
    phase, pcm, sequence, observations = 'before', bytearray(), 0, []
    before = after = None
    for line in lines:
        diagnostic = status(line)
        if diagnostic is not None:
            if phase == 'before':
                before = diagnostic
            else:
                observations.append(diagnostic)
                if phase == 'after' and after is None:
                    after = diagnostic
        if 'wake_pcm:' not in line:
            if phase == 'capture' and any(tag in line for tag in
                    ('Guru Meditation', 'Brownout', 'Backtrace:', 'ESP-ROM:')):
                raise ValueError('Reset/crash during capture')
            continue
        payload = line.split('wake_pcm:', 1)[1].strip()
        if payload == 'begin rate=16000 samples=64000':
            if phase != 'before' or before is None:
                raise ValueError('Exactly one capture with preceding status required')
            phase = 'capture'
        elif payload == 'done':
            if phase != 'capture' or len(pcm) != 128000:
                raise ValueError('Incomplete or misplaced capture end')
            phase = 'after'
        else:
            match = re.fullmatch(r'seq=(\d+) count=(\d+) data=(\S+)', payload)
            if phase != 'capture' or match is None:
                raise ValueError('Malformed or out-of-window PCM packet')
            seq, count = map(int, match.group(1, 2))
            try:
                chunk = base64.b64decode(match[3], validate=True)
            except binascii.Error as error:
                raise ValueError('Invalid PCM Base64') from error
            if seq != sequence or not 1 <= count <= 160 or len(chunk) != count * 2:
                raise ValueError('Missing/duplicate packet or PCM byte-count mismatch')
            pcm.extend(chunk)
            sequence += 1
            if len(pcm) > 128000:
                raise ValueError('Capture exceeds four seconds')
    if phase != 'after' or after is None:
        raise ValueError('Complete capture and following status required')
    previous = before
    for item in [before, *observations]:
        if any(item[key] != 0 for key in ('state', 'muted', 'upload')):
            raise ValueError('Capture must stay unmuted idle with upload disabled')
        if any(item[key] != before[key] for key in FIXED):
            raise ValueError('Upload, reconnect or wake-error/drop counters changed')
        if item['uptime_ms'] < previous['uptime_ms']:
            raise ValueError('Device restarted during capture')
        previous = item
    return bytes(pcm), {'samples': 64000, 'rate': 16000, 'channels': 1,
        'sample_width_bytes': 2, 'packets': sequence,
        'source_log_sha256': hashlib.sha256(raw).hexdigest(),
        'pcm_sha256': hashlib.sha256(pcm).hexdigest(),
        'observed_upload_counters_unchanged': True,
        'bounded_transport_integrity_passed': True,
        'role': 'local-family-TEST-only-unlabelled',
        'TRAIN_or_calibration_or_model_selection_allowed': False,
        'consent_or_freshness_or_content_proven_by_extraction': False,
        'model_scored': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-log', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True,
                        help='New private directory; existing paths are rejected')
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        parser.error('TEST audio output must stay outside the source repository')
    os.umask(0o077)
    pcm, proof = decode_capture(args.private_log.read_bytes())
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    with wave.open(str(args.output / 'TEST-only.wav'), 'wb') as audio:
        audio.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        audio.writeframes(pcm)
    (args.output / 'transport-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'transport_integrity_passed': True, 'samples': 64000,
                      'model_scored': False, 'TEST_admitted': False}))


if __name__ == '__main__':
    main()
