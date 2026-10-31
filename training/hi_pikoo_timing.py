#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Audit fictional TRAIN/DEV timing; never repair missing or extra words.

Original WAVs stay immutable. The bounded view removes only low-energy exterior
padding, keeps 200ms before/300ms after activity, and never cuts between words.
It is an energy estimate, not a gold phoneme or age annotation.
"""
import argparse
import json
from pathlib import Path
import numpy as np


def timing(pcm):
    x = np.asarray(pcm, np.float64)
    if not len(x):
        raise ValueError('Empty synthetic waveform')
    chunks = np.pad(x, (0, (-len(x)) % 320)).reshape(-1, 320)
    rms = np.sqrt(np.mean(chunks*chunks, axis=1))
    threshold = max(5., float(rms.max())*.05)
    active = np.flatnonzero(rms >= threshold)
    if not len(active):
        raise ValueError('No measurable synthetic speech')
    first, last = int(active[0])*320, min(len(x), (int(active[-1])+1)*320)
    start, end = max(0, first-3200), min(len(x), last+4800)
    return {'raw_samples': len(x), 'active_start_sample': first,
        'active_end_sample': last, 'view_start_sample': start,
        'view_end_sample': end, 'endpoint_sample': min(len(x), last+640),
        'raw_ms': len(x)/16, 'active_span_ms': (last-first)/16,
        'view_ms': (end-start)/16, 'tail_ms': (len(x)-last)/16,
        'removed_exterior_ms': (len(x)-(end-start))/16,
        'preferred_1_to_2_seconds': 1000 <= (last-first)/16 <= 2000,
        'method': 'RMS20ms-peakMinus26dB-head200ms-tail300ms-v1'}


def view(pcm):
    details = timing(pcm)
    start, end = details['view_start_sample'], details['view_end_sample']
    return np.asarray(pcm)[start:end].copy(), details


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True, action='append')
    p.add_argument('--protected-hashes', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    from hi_pikoo_review import validate
    from hi_pikoo_train import read_audio
    protected = set(json.loads(a.protected_hashes.read_text())['audio_sha256'].values())
    records = []
    seen = set()
    for manifest in a.manifest:
        for row in json.loads(manifest.read_text()):
            path = validate(row, manifest.parent, protected)
            if row['sha256'] in seen:
                continue
            seen.add(row['sha256'])
            try:
                result = timing(read_audio(path))
            except ValueError as error:
                result = {'timing_error': str(error)}
            records.append({'id': row.get('id'), 'sha256': row['sha256'],
                'split': row['split'], 'label_as_generated': row['label'], **result})
    spans = [r['active_span_ms'] for r in records if 'active_span_ms' in r]
    summary = {'records': len(records), 'median_active_span_ms': float(np.median(spans)),
        'exterior_padding_over_300ms': sum(r.get('removed_exterior_ms', 0)>300 for r in records),
        'household_used': False, 'new_test': False, 'original_audio_modified': False,
        'content_admission_not_implied': True, 'records_detail': records}
    a.output.write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'records_detail'}))


if __name__ == '__main__':
    main()
