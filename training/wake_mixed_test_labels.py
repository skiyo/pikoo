#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Assemble, label and seal the fixed TEST using human CONTENT observations.

No microphone, provider, model inference or model selection. Missing and failed
attempts remain visible; labels never come from prompts or KWS predictions.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

from wake_mixed_test import ROOT, inside, protocol, sha, validate_bundle

HEARD = ('hi-piku', 'hi-piko', 'hi-alone', 'name-alone', 'Tikoo', 'nihao-Pikoo',
         'ordinary-English', 'ordinary-Chinese', 'invalid-or-unclear')


def write(path, value):
    descriptor, temp = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w') as output:
            json.dump(value, output, ensure_ascii=False, indent=2)
            output.write('\n')
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)


def binding(plan, protocol_sha256):
    return {'protocol_sha256': protocol_sha256, 'model_sha256': plan['model_sha256'],
            'policy_sha256': plan['policy_sha256']}


def assemble(plan, root):
    """All 150 slots remain present, including empty/failed source attempts."""
    root = root.resolve()
    source = root / 'synthetic/manifest.json'
    rows = json.loads(source.read_text()) if source.exists() else []
    if len(rows) != len({row['id'] for row in rows}):
        raise ValueError('Duplicate synthetic source attempts')
    sources = {row['id']: row for row in rows}
    if set(sources) - {s['id'] for s in plan['slots'] if s['source_kind'] == 'synthetic'}:
        raise ValueError('Unexpected synthetic attempts outside fixed protocol')
    result = []
    for slot in plan['slots']:
        row = {'id': slot['id'], 'status': 'missing-not-captured', 'split': 'test',
            'evaluation_only': True, 'frozen_holdout': True, 'training_or_tuning_allowed': False,
            'model_scored': False, 'cloud_uploaded': False, 'source_audition': False,
            'source_kind': slot['source_kind'], 'speaker': slot['speaker'],
            'frozen_model_sha256': plan['model_sha256']}
        if slot['source_kind'] == 'synthetic' and slot['id'] in sources:
            original = sources[slot['id']]
            if original.get('speaker') != slot['speaker'] or original.get('frozen_model_sha256') != plan['model_sha256']:
                raise ValueError('Synthetic source metadata differs from frozen plan')
            row.update(original)
            if original['status'] == 'recorded':
                path = inside(root / 'synthetic', original['path'])
                if sha(path) != original['sha256']:
                    raise ValueError('Synthetic raw waveform changed')
                row['path'] = str(path.relative_to(root))
        elif slot['source_kind'] == 'family':
            # The future capture session is explicitly placed at its fixed slot.
            folder = root / 'captures' / slot['id']
            metadata = folder / 'capture.json'
            if metadata.exists():
                capture = json.loads(metadata.read_text())
                if (capture.get('speaker_id') != slot['speaker'] or
                        capture.get('speaker_role_user_declared') != slot['role'] or
                        capture.get('prompt') != slot['prompt']):
                    raise ValueError('Family capture slot/speaker/prompt differs')
                row.update(status='recorded' if capture['status']=='captured-unlabelled-not-scored'
                    else 'failed-or-interrupted-capture',
                    capture_metadata_path=str(metadata.relative_to(root)))
                if row['status'] == 'recorded':
                    path = folder / 'TEST-only.wav'
                    row.update(path=str(path.relative_to(root)), sha256=sha(path),
                        created_at=capture['completed_at'], synthetic=False,
                        real_child=slot['role']=='child', family_inputs_used=True,
                        reference_audio_used=False)
        result.append(row)
    return result


def record_label(draft, plan, protocol_sha256, row, heard, age, accent, valid,
                 no_extra, completion_ms=None, reviewed_at=None):
    if heard not in HEARD or age not in ('adult', 'child', 'unknown') or accent not in ('standard', 'Chinese-accent', 'unknown'):
        raise ValueError('Explicit human content/age/accent observations required')
    wanted = binding(plan, protocol_sha256)
    if draft is None:
        draft = {**wanted, 'model_scored': False, 'records': []}
    if (any(draft.get(k) != v for k, v in wanted.items()) or draft.get('model_scored') is not False):
        raise ValueError('Draft bound to another candidate/protocol or already scored')
    if row.get('status') != 'recorded':
        raise ValueError('Cannot invent a content label for a missing/failed capture')
    stamp = reviewed_at or datetime.now(timezone.utc).isoformat()
    target = heard in ('hi-piku', 'hi-piko')
    if target and (type(completion_ms) not in (int, float) or not 0 < completion_ms < float('inf')):
        raise ValueError('Full target needs a pre-score content endpoint')
    item = {'id': row['id'], 'sha256': row['sha256'], 'heard': heard,
        'actual_label': int(target), 'actual_variant': heard.removeprefix('hi-') if target else 'non-target',
        'actual_age': age, 'actual_accent': accent, 'quality_valid': bool(valid),
        'complete_hi_and_name': target, 'no_repetition_or_extra_words': bool(no_extra),
        'completion_ms': completion_ms if target else None,
        'negative_category': None if target else heard, 'reviewed_at': stamp}
    records = list(draft['records'])
    prior = next((r for r in records if r['id'] == row['id']), None)
    if prior and prior['sha256'] != row['sha256']:
        raise ValueError('Waveform replaced after human review; keep original attempt')
    records = [r for r in records if r['id'] != row['id']] + [item]
    return {**draft, 'records': records}


def seal(plan, rows, draft, root, policy, policy_sha256, protected, protected_sha256,
         manifest_sha256, protocol_sha256):
    wanted = binding(plan, protocol_sha256)
    if any(draft.get(k) != v for k, v in wanted.items()) or draft.get('model_scored') is not False:
        raise ValueError('Unscored candidate-bound content labels required')
    report = {**wanted, 'manifest_sha256': manifest_sha256,
        'labels_committed_before_model_scores': True, 'model_scored': False,
        'reviewed_by': 'human-content-only', 'reviewed_at': datetime.now(timezone.utc).isoformat(),
        'records': draft['records']}
    validate_bundle(plan, rows, report, root, policy, policy_sha256,
        protected, protected_sha256, manifest_sha256, protocol_sha256)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('assemble', 'label', 'seal'))
    for name in ('protocol', 'policy', 'model', 'protected-hashes'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--case-id')
    parser.add_argument('--heard', choices=HEARD)
    parser.add_argument('--age', choices=('adult', 'child', 'unknown'))
    parser.add_argument('--accent', choices=('standard', 'Chinese-accent', 'unknown'))
    parser.add_argument('--quality', choices=('valid', 'invalid'))
    parser.add_argument('--no-repetition-or-extra-words', action='store_true')
    parser.add_argument('--completion-ms', type=float)
    args = parser.parse_args(); os.umask(0o077)
    from hi_pikoo_sealed_review import frozen
    policy = frozen(args.model, args.policy)
    plan = json.loads(args.protocol.read_text()); root = args.protocol.resolve().parent
    if root.is_relative_to(ROOT):
        raise ValueError('Private TEST bundle must stay outside the repository')
    if plan != protocol(policy, sha(args.policy), sha(args.protected_hashes), plan['declared_at']):
        raise ValueError('Protocol/policy/protection snapshot changed')
    if any((args.policy.parent / name).exists() for name in
           ('sealed-test-consumption.json', 'independent-TEST-consumption.json')):
        raise ValueError('TEST already consumed; labels cannot change after predictions')
    manifest = root / 'manifest.json'; draft_path = root / 'human-review.draft.json'
    sealed = root / 'human-review.json'
    if sealed.exists() and json.loads(sealed.read_text()).get('labels_committed_before_model_scores'):
        raise ValueError('Content review already sealed; no silent replacement')
    if args.action == 'assemble':
        rows = assemble(plan, root); write(manifest, rows)
        print(json.dumps({'slots': len(rows), 'recorded': sum(r['status']=='recorded' for r in rows),
            'missing_or_failed': sum(r['status']!='recorded' for r in rows), 'model_scored': False}))
        return
    rows = json.loads(manifest.read_text())
    draft = json.loads(draft_path.read_text()) if draft_path.exists() else None
    if args.action == 'label':
        if not all((args.case_id, args.heard, args.age, args.accent, args.quality)):
            raise ValueError('Case ID, heard content, actual age/accent and quality required')
        row = next(r for r in rows if r['id'] == args.case_id)
        if row.get('status') != 'recorded':
            raise ValueError('Cannot label a missing/failed TEST attempt')
        if sha(inside(root, row['path'])) != row['sha256']:
            raise ValueError('Original waveform changed')
        updated = record_label(draft, plan, sha(args.protocol), row, args.heard, args.age,
            args.accent, args.quality=='valid', args.no_repetition_or_extra_words, args.completion_ms)
        event = updated['records'][-1]
        with (root / 'human-review.events.jsonl').open('a') as output:
            output.write(json.dumps({**binding(plan, sha(args.protocol)), 'record': event}) + '\n')
        write(draft_path, updated)
        print(json.dumps({'labelled': len(updated['records']), 'model_scored': False}))
    else:
        if draft is None:
            raise ValueError('No human content labels; cannot seal TEST')
        protection = json.loads(args.protected_hashes.read_text())
        report = seal(plan, rows, draft, root, policy, sha(args.policy),
            set(protection['audio_sha256'].values()), sha(args.protected_hashes), sha(manifest), sha(args.protocol))
        write(sealed, report)
        print(json.dumps({'content_review_sealed': True, 'cases': len(rows), 'model_scored': False}))


if __name__ == '__main__': main()
