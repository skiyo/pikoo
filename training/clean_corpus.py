#!/usr/bin/env python3
"""Create a content-clean development manifest without deleting source audio.

Decisions use transcript/provenance evidence only, never wake-model scores.
Disagreement means quarantine, not an automatic correction of the label. ASR
agreement cannot verify lexical tone, speaker age or real-device performance.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import re

from review_local_corpus import content_approved


RULE = 'content-quarantine-v1'
PUBLIC_CORPORA = {'ChildMandarin', 'PolyAI-MInDS14-zh-CN'}
LEGACY = {'macOS-aligned-v2', 'macOS-local-synthetic',
          'known-self-test-v1-development', 'known-self-test-v1-validation'}
SYNTHETIC = {'Qwen3-TTS-synthetic-local', 'Google-Gemini-TTS-synthetic',
             'Google-TTS-level-tone-synthetic', 'Google-TTS-incomplete-prefix',
             'TTS-matched-incomplete-prefix', 'pitch-tempo-augmented-Qwen3-TTS',
             'pitch-tempo-augmented-Google-TTS', 'pitch-tempo-augmented-Google-level-tone'}


def parents(row):
    values = {row.get('parent_sha256'),
              (row.get('augmentation') or {}).get('parent_sha256')}
    return values - {None, ''}


def guard(rows, protected):
    """Check metadata before any waveform is opened, including ancestors."""
    for row in rows:
        if (row['sha256'] in protected or parents(row) & protected
                or row.get('split') not in {'train', 'validation'}
                or row.get('evaluation_only') or row.get('frozen_holdout')
                or row.get('family_inputs_used') or row.get('reference_audio_used')
                or str(row.get('source', '')).startswith('private-')):
            raise ValueError('Protected/private/test data cannot enter corpus cleaning')


def clean(rows, reviews, protected=(), catalog=(), signal_findings=()):
    """Return unchanged approved rows and a reversible exclusion report.

    Optional catalog supplies absent parent metadata, not additional training
    examples. All supplied evidence is considered, including disagreements.
    Latin-spelled positive synthesis needs two different recognizer families;
    two local reruns of one recognizer do not constitute independent evidence.
    """
    protected = set(protected)
    guard(rows, protected)
    guard(catalog, protected)
    metadata = {}
    for row in [*catalog, *rows]:
        digest = row['sha256']
        if row.get('label') not in (0, 1):
            raise ValueError('Invalid binary label')
        if digest in metadata:
            old = metadata[digest]
            for key in ['label', 'split', 'group', 'speaker', 'text']:
                if old.get(key) != row.get(key):
                    raise ValueError('Conflicting waveform label/split/provenance')
            if parents(old) != parents(row):
                raise ValueError('Conflicting waveform ancestors')
        metadata[digest] = row
    speakers = {}
    for row in metadata.values():
        speaker = row.get('group') or row.get('speaker')
        if not speaker:
            raise ValueError('Missing speaker group')
        if speaker in speakers and speakers[speaker] != row['split']:
            raise ValueError('Speaker group crosses splits')
        speakers[speaker] = row['split']
    evidence = defaultdict(list)
    for record in reviews:
        if record['sha256'] in protected:
            raise ValueError('Protected review cannot guide cleaning')
        if record['sha256'] not in metadata:
            raise ValueError('Review lacks eligible source metadata')
        if not isinstance(record.get('transcript'), str) or not record.get('model'):
            raise ValueError('Review requires verbatim transcript and recognizer identity')
        evidence[record['sha256']].append(record)
    reasons = defaultdict(set)
    for digest, row in metadata.items():
        source = row.get('source')
        if source in LEGACY:
            reasons[digest].add('legacy-synthesis-without-current-content-audit')
        elif source in PUBLIC_CORPORA:
            if row['label'] != 0:
                raise ValueError('Public conversation corpus must not create wake positives')
        elif source not in SYNTHETIC or not row.get('synthetic') or row.get('real_child'):
            reasons[digest].add('unverified-source')
        records = evidence[digest]
        for record in records:
            if record.get('label', row['label']) != row['label']:
                raise ValueError('Review label differs from source')
            if (not content_approved(row, record['transcript'])
                    or record.get('approved') is False
                    or record.get('local_approved') is False
                    or record.get('prior_approved') is False):
                reasons[digest].add('content-review-disagreement')
        ancestor = parents(row)
        # Pitch/tempo variants inherit a reviewed parent's content, but cuts
        # require their own review: a parent transcript cannot prove a prefix.
        cut = ('incomplete-prefix' in str(source)
               or row.get('mined_training_prefix'))
        if source not in PUBLIC_CORPORA | LEGACY:
            if (not str(source).startswith('pitch-tempo-augmented-') or cut) and not records:
                reasons[digest].add('missing-content-review')
            if not ancestor and row['label'] and re.search('[A-Za-z]', row.get('text', '')):
                families = set()
                for record in records:
                    model = record['model'].lower()
                    if 'qwen' in model:
                        families.add('qwen')
                    elif 'gemini' in model or 'google' in model:
                        families.add('google')
                if len(families) < 2:
                    reasons[digest].add('latin-target-awaiting-independent-content-review')
        if ancestor - metadata.keys():
            reasons[digest].add('missing-parent-provenance')
    for finding in signal_findings:
        digest = finding['sha256']
        if digest not in metadata or digest in protected:
            raise ValueError('Signal evidence lacks eligible source metadata')
        if finding['reason'] not in {'empty-or-nearly-silent', 'severe-digital-clipping',
                                     'invalid-pcm-format', 'malformed-waveform'}:
            raise ValueError('Unknown signal quality rule')
        reasons[digest].add(finding['reason'])
    # Detect ancestry cycles even when another reason would already exclude it.
    visited, active = set(), set()
    def visit(digest):
        if digest in active:
            raise ValueError('Cyclic augmentation ancestry')
        if digest in visited:
            return
        active.add(digest)
        for parent in sorted(parents(metadata[digest]) & metadata.keys()):
            if metadata[parent]['split'] != metadata[digest]['split']:
                raise ValueError('Augmentation ancestor crosses splits')
            row = metadata[digest]
            if (str(row['source']).startswith('pitch-tempo-augmented-')
                    and parent == (row.get('augmentation') or {}).get('parent_sha256')):
                if (row['label'], row.get('text'), row.get('group')) != (
                        metadata[parent]['label'], metadata[parent].get('text'), metadata[parent].get('group')):
                    raise ValueError('Pitch/tempo variant changed parent label/content/group')
            visit(parent)
            if reasons[parent]:
                reasons[digest].add('quarantined-ancestor:' + parent)
        active.remove(digest)
        visited.add(digest)
    for digest in metadata:
        visit(digest)
    approved = [dict(row) for row in rows if not reasons[row['sha256']]]
    rejected = [{'sha256': row['sha256'], 'label': row['label'],
                 'split': row['split'], 'source': row['source'],
                 'reasons': sorted(reasons[row['sha256']])}
                for row in rows if reasons[row['sha256']]]
    return approved, {'rule': RULE, 'input_rows': len(rows),
        'retained_rows': len(approved), 'quarantined_rows': len(rejected),
        'reason_counts': dict(Counter(reason.split(':')[0]
            for row in rejected for reason in row['reasons'])),
        'retained_counts': dict(Counter(f"{r['split']}:{r.get('synthetic_style', 'other')}:label={r['label']}"
            for r in approved)), 'quarantine': rejected,
        'labels_changed': 0, 'source_files_deleted': 0,
        'model_scores_used': False, 'independent_or_household_used': False,
        'limitations': 'ASR screening is not tone, child, human or hardware acceptance'}


def signal_issue(path):
    """Conservative PCM corruption checks, not a speech-content classifier."""
    import wave
    import numpy as np
    try:
        with wave.open(str(path), 'rb') as audio:
            if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 16000):
                return 'invalid-pcm-format'
            expected = audio.getnframes()
            pcm = np.frombuffer(audio.readframes(expected), dtype='<i2').astype(np.float64)
            if len(pcm) != expected:
                return 'malformed-waveform'
    except (wave.Error, EOFError, ValueError):
        return 'malformed-waveform'
    if not len(pcm) or np.sqrt(np.mean(pcm * pcm)) < 1:
        return 'empty-or-nearly-silent'
    # One percent hard-clipped samples is already severe distortion. Lower
    # clipping, loudness, final-phoneme completeness and noise need other QA.
    if np.mean(np.abs(pcm) >= 32760) >= .01:
        return 'severe-digital-clipping'
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--reviews', type=Path, required=True,
                        help='Flat eligible content reviews with model identity')
    parser.add_argument('--catalog', type=Path,
                        help='Optional eligible metadata for absent ancestors')
    parser.add_argument('--protected-hashes', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    rows = json.loads(args.manifest.read_text())
    catalog = json.loads(args.catalog.read_text()) if args.catalog else []
    protected = set(json.loads(args.protected_hashes.read_text())['audio_sha256'].values())
    reviews = json.loads(args.reviews.read_text())
    clean(rows, reviews, protected, catalog)
    # Only after every metadata/ancestor guard passed may source hashes be read.
    findings = []
    for row in rows:
        path = (args.manifest.parent / row['path']).resolve()
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Changed source waveform')
        issue = signal_issue(path)
        if issue:
            findings.append({'sha256': row['sha256'], 'reason': issue})
    approved, report = clean(rows, reviews, protected, catalog, findings)
    if args.output.exists():
        raise ValueError('Output already exists; preserve the previous cleaning version')
    args.output.mkdir(parents=True)
    for row in approved:
        row['path'] = os.path.relpath((args.manifest.parent / row['path']).resolve(), args.output.resolve())
    report.update(source_manifest_sha256=hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
                  reviews_sha256=hashlib.sha256(args.reviews.read_bytes()).hexdigest(),
                  protected_ledger_sha256=hashlib.sha256(args.protected_hashes.read_bytes()).hexdigest())
    report['signal_findings'] = findings
    (args.output / 'manifest.json').write_text(json.dumps(approved, ensure_ascii=False, indent=2) + '\n')
    (args.output / 'cleaning-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'quarantine'}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
