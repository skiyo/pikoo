#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prospective content-only repair of four rejected synthetic TEST sources.

Never synthesizes, infers, records, or changes a protocol/model/threshold. A new
benchmark attempt is distinct from its recipe audition. Original attempts and
their human rejection remain immutable and all 150 scoring slots remain required.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import wave

from wake_mixed_test import ROOT, inside, protocol, sha, timestamp

SCOPE = 'pre-score-synthetic-source-repair-v1'
FOLLOWUP_SCOPE = 'pre-score-single-rejected-source-followup-v1'
SLOTS = ('TEST-057', 'TEST-068', 'TEST-074', 'TEST-077')
RECIPE = 'literal-target-response-v2'


def unconsumed(policy_path, root, allow_sealed=False):
    if any((policy_path.parent / name).exists() for name in
           ('sealed-test-consumption.json', 'independent-TEST-consumption.json')):
        raise ValueError('Consumed TEST cannot be repaired or called fresh')
    for name in ('human-review.json', 'human-review.source-repair1.json', 'human-review.source-repair2.json'):
        path = root / name
        if not allow_sealed and path.exists() and json.loads(path.read_text()).get('labels_committed_before_model_scores') is True:
            raise ValueError('Do not amend a sealed content review')


def evidence(root, reference):
    path = inside(root, reference['path'])
    if sha(path) != reference['sha256']:
        raise ValueError('Source repair evidence changed')
    return json.loads(path.read_text())


def ref(root, path):
    return {'path': str(path.resolve().relative_to(root.resolve())), 'sha256': sha(path)}


def pcm_hash(path):
    with wave.open(str(path)) as f:
        return hashlib.sha256(f.readframes(f.getnframes())).hexdigest()


def recipe_records(pilots, review, base, plan, declared_at):
    if (len(pilots) != 4 or len(review.get('records', [])) != 4 or
            review.get('reviewed_by') != 'human-content-only' or
            review.get('model_scored') is not False or
            not isinstance(review.get('human_statement'), str) or not review['human_statement'].strip() or
            not timestamp(plan['declared_at']) < timestamp(review['reviewed_at']) < timestamp(declared_at)):
        raise ValueError('All four recipe auditions need actual pre-score human content review')
    labels = {r['request_id']: r for r in review['records']}
    if len(labels) != 4 or set(labels) != {r['request_id'] for r in pilots}:
        raise ValueError('Human recipe labels must match exactly four audition IDs')
    if {p.get('old_TEST_slot') for p in pilots} != set(SLOTS):
        raise ValueError('Only the four rejected source recipes may be amended')
    slots = {s['id']: s for s in plan['slots']}
    requests = []
    for pilot in sorted(pilots, key=lambda p: p['old_TEST_slot']):
        slot_id = pilot['old_TEST_slot']; slot = slots[slot_id]
        label = labels[pilot['request_id']]; original = base[slot_id]
        wanted = slot['prompt'].split()[1]
        if (pilot.get('generation_request_policy') != RECIPE or
                pilot.get('TRAIN_allowed') is not False or pilot.get('wake_model_scored') is not False or
                pilot.get('synthetic') is not True or pilot.get('family_inputs_used') is not False or
                label.get('sha256') != pilot['sha256'] or
                label.get('actual_variant') != wanted or label.get('actual_age') != 'adult' or
                label.get('actual_accent') != 'standard' or label.get('quality_valid') is not True or
                label.get('complete_hi_and_name') is not True or
                label.get('no_repetition_or_extra_words') is not True or
                timestamp(pilot['created_at']) > timestamp(review['reviewed_at']) or
                pilot.get('old_source_sha256') != original['sha256'] or
                'openai:' + pilot['voice'] != slot['speaker'] or original['speaker'] != slot['speaker']):
            raise ValueError('Recipe pronunciation, actual age/accent or source evidence is not approved')
        requests.append({'id': slot_id, 'request_id': 'r12-TEST-source-amend1-' + slot_id,
            'old_source_sha256': original['sha256'], 'recipe_audition_id': pilot['request_id'],
            'recipe_audition_sha256': pilot['sha256'], 'voice': pilot['voice'],
            'text': 'Hi, Pikoo!' if wanted == 'piku' else 'Hi, Pico!',
            'generation_request_policy': RECIPE, 'style': pilot['style']})
    return requests


def declaration(plan, policy_path, root, rejection_path, pilot_manifest, recipe_review,
                declared_at=None, allow_sealed=False):
    """Only explicit human observations unlock a prospective, one-attempt plan."""
    unconsumed(policy_path, root, allow_sealed)
    policy = json.loads(policy_path.read_text())
    if plan != protocol(policy, sha(policy_path), plan['protected_registry_sha256'], plan['declared_at']):
        raise ValueError('Complete unchanged protocol and frozen policy required')
    base_path = root / 'synthetic/manifest.json'; base_rows = json.loads(base_path.read_text())
    base = {r['id']: r for r in base_rows}
    expected = {s['id'] for s in plan['slots'] if s['source_kind'] == 'synthetic'}
    if len(base_rows) != 70 or set(base) != expected:
        raise ValueError('Preserve all original70 source attempts')
    rejected = json.loads(rejection_path.read_text())
    if (rejected.get('all_four_complete_targets_rejected') is not True or
            len(rejected.get('records', [])) != 4 or
            {r['id'] for r in rejected['records']} != set(SLOTS)):
        raise ValueError('Explicit human rejection of the original four targets required')
    for row in rejected['records']:
        old = base[row['id']]
        if old.get('status') != 'recorded' or row['sha256'] != old['sha256'] or sha(inside(root / 'synthetic', old['path'])) != row['sha256']:
            raise ValueError('Keep every original rejected source unchanged')
    pilots = json.loads(pilot_manifest.read_text())
    for pilot in pilots:
        if sha(inside(pilot_manifest.parent, pilot['path'])) != pilot['sha256']:
            raise ValueError('Recipe audition raw source changed')
    review = json.loads(recipe_review.read_text())
    stamp = declared_at or datetime.now(timezone.utc).isoformat()
    if not timestamp(rejected['at']) < timestamp(review['reviewed_at']):
        raise ValueError('Human rejection must precede recipe review')
    requests = recipe_records(pilots, review, base, plan, stamp)
    return {'schema_version': 1, 'scope': SCOPE, 'declared_at': stamp,
        'protocol_sha256': sha(root / 'protocol.json'), 'policy_sha256': sha(policy_path),
        'model_sha256': plan['model_sha256'], 'fixed_policy': plan['fixed_policy'],
        'original_source_manifest': ref(root, base_path),
        'human_original_rejection': ref(root, rejection_path),
        'recipe_audition_manifest': ref(root, pilot_manifest), 'human_recipe_review': ref(root, recipe_review),
        'model_scored': False, 'maximum_attempts_each': 1, 'automatic_retry': False,
        'whole_TEST_slots': 150, 'actual_target_cohorts': 6, 'targets_per_actual_cohort': 20,
        'negative_slots': 30, 'family_slots_still_required': 80,
        'auditions_cannot_be_benchmark_sources': True, 'requests': requests}


def validate_declaration(value, plan, policy_path, root):
    if value.get('scope') == FOLLOWUP_SCOPE:
        evidence(root, value['previous_repair_plan'])
        evidence(root, value['human_previous_round_review'])
        expected = followup_declaration(plan, policy_path, root,
            inside(root, value['previous_repair_plan']['path']),
            inside(root, value['human_previous_round_review']['path']),
            value['declared_at'], allow_sealed=True)
        if value != expected:
            raise ValueError('Single source follow-up changed or weakens TEST scope')
        return value
    for name in ('original_source_manifest', 'human_original_rejection',
                 'recipe_audition_manifest', 'human_recipe_review'):
        evidence(root, value[name])
    expected = declaration(plan, policy_path, root,
        inside(root, value['human_original_rejection']['path']),
        inside(root, value['recipe_audition_manifest']['path']),
        inside(root, value['human_recipe_review']['path']), value['declared_at'], allow_sealed=True)
    if value != expected:
        raise ValueError('Repair plan changed or weakens fixed TEST scope')
    return value


def repair_round(value):
    if value.get('scope') == SCOPE:
        return 1
    if value.get('scope') == FOLLOWUP_SCOPE:
        return 2
    raise ValueError('Unknown bounded source repair scope')


def followup_declaration(plan, policy_path, root, previous_plan, human_review,
                         declared_at=None, allow_sealed=False):
    """One extra attempt for human-rejected RT3; never an automatic retry loop."""
    unconsumed(policy_path, root, allow_sealed)
    prior = json.loads(previous_plan.read_text())
    if repair_round(prior) != 1:
        raise ValueError('Only one follow-up round is allowed')
    validate_declaration(prior, plan, policy_path, root)
    previous = repaired_rows(plan, root, policy_path, previous_plan)
    review = json.loads(human_review.read_text()); labels = review.get('records', [])
    stamp = declared_at or datetime.now(timezone.utc).isoformat()
    if (review.get('reviewed_by') != 'human-content-only' or review.get('model_scored') is not False or
            not isinstance(review.get('human_statement'), str) or not review['human_statement'].strip() or
            len(labels) != 4 or {r['id'] for r in labels} != set(previous) or
            not timestamp(prior['declared_at']) < timestamp(review['reviewed_at']) < timestamp(stamp)):
        raise ValueError('Actual content review of all four previous attempts required')
    rejected = []
    for label in labels:
        row = previous[label['id']]
        if (label.get('sha256') != row['sha256'] or label.get('request_id') != row['request_id'] or
                label.get('model_scored') is not False or
                timestamp(row['created_at']) > timestamp(review['reviewed_at'])):
            raise ValueError('Human follow-up review differs from previous raw sources')
        if label['id'] == 'TEST-074':
            if (label.get('complete_hi_and_name') is not False or label.get('quality_valid') is not False or
                    label.get('heard') != 'hi-alone' or label.get('actual_label') != 0):
                raise ValueError('RT3 must be explicitly human-rejected as Hi only')
            rejected.append(label['id'])
        elif (label.get('complete_hi_and_name') is not True or label.get('quality_valid') is not True or
              label.get('actual_label') != 1 or label.get('actual_age') != 'adult' or
              label.get('actual_accent') != 'standard' or label.get('no_repetition_or_extra_words') is not True):
            raise ValueError('Keep the other three human-accepted sources unchanged')
    if rejected != ['TEST-074']:
        raise ValueError('Only the single human-rejected RT3 slot may receive a follow-up')
    request = next(r for r in prior['requests'] if r['id'] == 'TEST-074')
    request = {**request, 'request_id': 'r12-TEST-source-amend2-TEST-074',
        'old_source_sha256': previous['TEST-074']['sha256']}
    return {**prior, 'scope': FOLLOWUP_SCOPE, 'declared_at': stamp,
        'previous_repair_plan': ref(root, previous_plan),
        'human_previous_round_review': ref(root, human_review),
        'additional_benchmark_attempts_including_previous_round': 5,
        'only_one_followup_round_allowed': True, 'previous_raw_attempts_retained': True,
        'requests': [request]}


def generation_rows(value, source_rows, plan_sha256):
    base = {r['id']: r for r in source_rows}
    return [{**base[r['id']], **{k: r[k] for k in ('request_id', 'voice', 'text', 'style')},
        'source_repair_plan_sha256': plan_sha256, 'generation_request_policy': RECIPE,
        'old_source_sha256': r['old_source_sha256'],
        'purpose': 'new-benchmark-source-not-recipe-audition'} for r in value['requests']]


def repaired_rows(plan, root, policy_path, repair_path):
    """Return four NEW, unlabelled raw benchmark attempts; never select by score."""
    root = root.resolve()
    value = validate_declaration(json.loads(repair_path.read_text()), plan, policy_path, root)
    round_number = repair_round(value)
    previous = repaired_rows(plan, root, policy_path, inside(root, value['previous_repair_plan']['path'])) if round_number == 2 else {}
    folder = root / ('source-repair' + str(round_number)); raw = json.loads((folder / 'manifest.json').read_text())
    requests = {r['id']: r for r in value['requests']}; actual = {r['id']: r for r in raw}
    if len(raw) != len(requests) or set(actual) != set(requests):
        raise ValueError(('Exactly four' if round_number == 1 else 'Exactly one') +
                         ' attempted replacements required; failures cannot disappear')
    pilots = evidence(root, value['recipe_audition_manifest'])
    original = evidence(root, value['original_source_manifest'])
    protected = {r['sha256'] for r in pilots + original if r.get('sha256')}
    protected_pcm = {pcm_hash(inside(root / 'synthetic', r['path'])) for r in original if r.get('status') == 'recorded'}
    pilot_root = inside(root, value['recipe_audition_manifest']['path']).parent
    protected_pcm.update(pcm_hash(inside(pilot_root, r['path'])) for r in pilots)
    protected.update(row['sha256'] for row in previous.values())
    protected_pcm.update(pcm_hash(inside(root, row['path'])) for row in previous.values())
    results = dict(previous)
    for id, row in actual.items():
        request = requests[id]
        if (row.get('status') != 'recorded' or row.get('request_id') != request['request_id'] or
                row.get('source_repair_plan_sha256') != sha(repair_path) or
                row.get('generation_request_policy') != RECIPE or
                row.get('old_source_sha256') != request['old_source_sha256'] or
                row.get('voice') != request['voice'] or row.get('text') != request['text'] or
                row.get('style') != request['style'] or row.get('model') != 'gpt-realtime-2.1-mini' or
                row.get('speaker') != 'openai:' + request['voice'] or
                row.get('model_scored') is not False or row.get('training_or_tuning_allowed') is not False or
                row.get('family_inputs_used') is not False or row.get('source_audition') is not False or
                timestamp(row['created_at']) <= timestamp(value['declared_at'])):
            raise ValueError('Repair must be a fresh, single planned benchmark attempt')
        path = inside(folder, row['path']); digest = sha(path)
        pcm_digest = pcm_hash(path)
        if digest != row['sha256'] or digest in protected or pcm_digest in protected_pcm:
            raise ValueError('Do not promote auditions, originals or duplicate raw sources')
        protected.add(digest)
        protected_pcm.add(pcm_digest)
        results[id] = {**row, 'path': str(path.relative_to(root))}
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('protocol', 'policy', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('rejection', 'pilot-manifest', 'recipe-review', 'previous-repair', 'previous-human-review'):
        parser.add_argument('--' + name, type=Path)
    args = parser.parse_args(); os.umask(0o077)
    root = args.protocol.resolve().parent
    followup = bool(args.previous_repair or args.previous_human_review)
    round_number = 2 if followup else 1
    if root.is_relative_to(ROOT) or args.output.resolve() != root / ('source-repair' + str(round_number) + '-plan.json'):
        raise ValueError('Use this private TEST bundle and a separate fixed plan file')
    plan = json.loads(args.protocol.read_text())
    if followup:
        if not args.previous_repair or not args.previous_human_review:
            raise ValueError('Both prior source plan and actual human content review required')
        value = followup_declaration(plan, args.policy, root, args.previous_repair, args.previous_human_review)
    else:
        if not all((args.rejection, args.pilot_manifest, args.recipe_review)):
            raise ValueError('Original rejection, audition manifest and human recipe review required')
        value = declaration(plan, args.policy, root, args.rejection, args.pilot_manifest, args.recipe_review)
    with args.output.open('x') as output:
        json.dump(value, output, indent=2); output.write('\n')
    print(json.dumps({'plan_written': True, 'planned_requests': len(value['requests']), 'API_called': False, 'model_scored': False}))


if __name__ == '__main__': main()
