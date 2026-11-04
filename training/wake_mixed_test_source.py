#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Validate the full frozen TEST protocol; emit ONLY its synthetic source slots.

No synthesis, key access, family recording or inference. The 70 emitted adult
clips cannot satisfy the 150-case TEST without real family cases and labels.
"""
import argparse
import json
from pathlib import Path
from wake_mixed_test import sha, protocol


def source_plan(plan, policy, protocol_sha256):
    if plan != protocol(policy, plan['policy_sha256'], plan['protected_registry_sha256'], plan['declared_at']):
        raise ValueError('Complete unchanged150-slot mixed TEST protocol required')
    texts = {
        'hi-alone': ['Hi!'] * 5,
        'name-alone': ['Pikoo!', 'Pico!', 'Pikoo!', 'Pico!', 'Pikoo!'],
        'Tikoo': ['Hi, Tee Koo!'] * 5,
        'missing-last-syllable': ['Hi, Pee!'] * 5,
        'nihao-Pikoo': ['你好，Pikoo。'] * 5,
        'ordinary-English': ['Please close the door.', 'The puppy is sleeping.',
            'What would you like to eat?', 'We can play after lunch.', 'Put the blue cup here.'],
        'ordinary-Chinese': ['我们一起玩积木吧。', '今天晚饭吃什么？', '电视声音小一点。',
            '你把水杯放在哪里了？', '哥哥正在看故事书。']}
    counts, rows = {}, []
    delivery = ['Casual connected everyday speech.', 'Slightly quick natural speech.',
                'Soft normal speech, no whispering.', 'A short natural greeting, no exaggerated vowels.']
    for slot in plan['slots']:
        if slot['source_kind'] != 'synthetic':
            continue
        if slot['expected_label']:
            text = 'Hi, Pee Koo!' if slot['prompt'] == 'Hi piku' else 'Hi, Pico!'
        else:
            category = slot['negative_category']; index = counts.get(category, 0)
            text = texts[category][index]; counts[category] = index + 1
        rows.append({'id': slot['id'], 'request_id': 'mixed-' + protocol_sha256[:12] + '-' + slot['id'],
            'voice': slot['speaker'].removeprefix('openai:'), 'speaker': slot['speaker'],
            'text': text, 'label': slot['expected_label'], 'source_kind': 'synthetic',
            'role': 'adult', 'accent': 'standard', 'intended_cohort': slot.get('intended_cohort'),
            'negative_category': slot.get('negative_category'),
            'actual_variant': None, 'actual_age': None, 'content_review': 'pending',
            'source_audition': False, 'split': 'test', 'evaluation_only': True,
            'frozen_holdout': True, 'training_or_tuning_allowed': False, 'model_scored': False,
            'synthetic': True, 'real_child': False, 'family_inputs_used': False,
            'reference_audio_used': False, 'cloud_uploaded': False,
            'frozen_model_sha256': policy['model_sha256'], 'protocol_sha256': protocol_sha256,
            'purpose': 'unscored-synthetic-sub-bundle-requires-full-mixed-TEST',
            'style': 'Read the supplied text exactly once, without commentary or repetition. '
                'Natural relaxed adult speech. Read English as everyday English and Chinese as Mandarin. '
                + delivery[len(rows) % len(delivery)]})
    if len(rows) != 70 or sum(row['label'] for row in rows) != 40:
        raise ValueError('Fixed synthetic sub-bundle changed')
    return rows


def preflight(args):
    from hi_pikoo_sealed_review import frozen
    from wake_test_isolation import validate as validate_isolation
    policy = frozen(args.model, args.policy)
    if any((args.policy.parent / name).exists() for name in
           ('sealed-test-consumption.json', 'independent-TEST-consumption.json')):
        raise ValueError('TEST consumed; no further source generation')
    proof = json.loads(args.native_proof.read_text())
    if (sha(args.native_proof) != policy['micro_proof_sha256'] or proof.get('passed') is not True or
            proof.get('model_sha256') != sha(args.model)):
        raise ValueError('Native parity proof changed')
    isolation = json.loads(args.isolation.read_text())
    if sha(args.isolation) != policy['test_isolation_sha256']:
        raise ValueError('Frozen speaker isolation changed')
    validate_isolation(isolation, [Path(p) for p in isolation['source_manifests_sha256']])
    if isolation['reserved_source_speakers'] != policy['required_fresh_test_speakers']:
        raise ValueError('Reserved TEST speakers differ')
    protection = json.loads(args.protected_hashes.read_text())
    for path, digest in protection['source_metadata_sha256'].items():
        if sha(Path(path)) != digest:
            raise ValueError('Prior recording metadata changed')
    plan = json.loads(args.protocol.read_text())
    if (plan['policy_sha256'] != sha(args.policy) or
            plan['protected_registry_sha256'] != sha(args.protected_hashes)):
        raise ValueError('Protocol must bind the exact policy/protection snapshot')
    rows = source_plan(plan, policy, sha(args.protocol))
    repair_path = getattr(args, 'source_repair', None)
    if repair_path:
        from wake_mixed_test_repair import validate_declaration, generation_rows, unconsumed, repair_round
        unconsumed(args.policy, args.protocol.resolve().parent)
        repair_value = json.loads(repair_path.read_text())
        round_number = repair_round(repair_value)
        if repair_path.resolve() != args.protocol.resolve().parent / ('source-repair' + str(round_number) + '-plan.json'):
            raise ValueError('Use only the private bundle source repair plan')
        repair = validate_declaration(repair_value, plan, args.policy, args.protocol.resolve().parent)
        rows = generation_rows(repair, rows, sha(repair_path))
    # Anchor billing to the already protected historical corpus, never a new
    # output folder's ledger. Refuse ambiguity instead of selecting a cheaper one.
    budget_roots = set()
    for source in protection['source_metadata_sha256']:
        parent = Path(source).resolve().parent
        ledger = parent / 'budget.json'
        if ledger.is_file() and json.loads(ledger.read_text()).get('cap_usd') == 2:
            budget_roots.add(str(parent))
    if len(budget_roots) != 1:
        raise ValueError('Exactly one protected historical cumulative $2 ledger required')
    result = {'scope': 'synthetic-source-sub-bundle-not-full-TEST',
        'protocol_sha256': sha(args.protocol), 'policy_sha256': sha(args.policy),
        'model_sha256': sha(args.model), 'whole_TEST_slots': 150, 'synthetic_slots': 70,
        'family_slots_still_required': 80, 'full_TEST_complete': False,
        'shared_budget_root': next(iter(budget_roots)), 'rows': rows}
    if repair_path:
        result.update(source_repair_plan_sha256=sha(repair_path), source_repair_requests=len(rows),
                      source_repair_round=round_number, source_repair_active_slots=4,
                      original70_sources_retained=True, automatic_retry=False)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('protocol', 'policy', 'model', 'protected-hashes', 'native-proof', 'isolation'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--source-repair', type=Path)
    print(json.dumps(preflight(p.parse_args())))


if __name__ == '__main__': main()
