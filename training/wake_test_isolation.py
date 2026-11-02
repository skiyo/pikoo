#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Reserve untouched synthetic speaker identities using metadata only.

Reads declared original TRAIN/DEV and consumed TEST manifests, never audio.
No synthesis, scoring, model selection or household inputs.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path

# Official Realtime voice list checked 2026-11-03; hold the two remaining
# identities rather than generating new clips from consumed ballad/verse.
RESERVED = ['openai:echo', 'openai:shimmer']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identities(manifests):
    used = set()
    for path in manifests:
        rows = json.loads(path.read_text())
        if not isinstance(rows, list):
            raise ValueError('Original synthetic manifest required')
        for row in rows:
            if (not row.get('synthetic') or row.get('real_child') or
                    row.get('family_inputs_used') or row.get('reference_audio_used')):
                raise ValueError('No real-person or family inputs in synthetic isolation metadata')
            if row['source'] == 'OpenAI-Realtime-synthetic':
                used.add(row['speaker'])
    return sorted(used)


def splits(manifests):
    return sorted({row['split'] for p in manifests for row in json.loads(p.read_text())})


def validate(isolation, manifests=None):
    if (isolation.get('target') != 'hi-piku-piko-v2' or
            isolation.get('reserved_source_speakers') != RESERVED or
            isolation.get('covered_splits') != ['test', 'train', 'validation'] or
            not isolation.get('declared_at') or isolation.get('metadata_only') is not True or
            isolation.get('audio_read') is not False or isolation.get('household_used') is not False):
        raise ValueError('Explicit predeclared fresh speaker isolation required')
    used = isolation['used_source_speakers']
    if set(RESERVED) & set(used) or len(used) != len(set(used)):
        raise ValueError('Fresh TEST identity already used')
    if manifests is not None:
        if {str(p.resolve()): sha(p) for p in manifests} != isolation['source_manifests_sha256']:
            raise ValueError('Source isolation manifest changed')
        if identities(manifests) != sorted(used):
            raise ValueError('Used speaker identities differ from source manifests')
        if splits(manifests) != isolation['covered_splits']:
            raise ValueError('TRAIN/DEV and consumed TEST source metadata required')
    return isolation


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, action='append', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); os.umask(0o077)
    value = {'target': 'hi-piku-piko-v2', 'declared_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'reserved_source_speakers': RESERVED, 'used_source_speakers': identities(a.manifest),
        'covered_splits': splits(a.manifest),
        'source_manifests_sha256': {str(p.resolve()): sha(p) for p in a.manifest},
        'metadata_only': True, 'audio_read': False, 'household_used': False}
    validate(value, a.manifest)
    with a.output.open('x') as file: json.dump(value, file, indent=2)
    print(json.dumps({'reserved': RESERVED, 'audio_read': False, 'TEST_generated': False}))


if __name__ == '__main__': main()
