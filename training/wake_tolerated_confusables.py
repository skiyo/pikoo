# SPDX-License-Identifier: Apache-2.0
"""Explicit full-greeting tolerance; never relabel a confusable as a target.

Retain and report all traces. Only independently admitted full Hi Tikoo/Tiko
DEV originals can be neutral under the user-declared revised policy. Ordinary
speech, incomplete greetings and all target-recall/early-wake gates remain.
No audio, model, network, household or TEST access.
"""
import hashlib
import json

from hi_pikoo_model import policy_metrics, event_scores
from hi_pikoo_review import normalized


POLICY = 'hi-piku-piko-v2-tolerant-t-v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path, manifest, protected_path):
    policy = json.loads(path.read_text())
    expected = {'revision': POLICY, 'positive_target': 'hi-piku-piko-v2',
                'accepted_names': ['piku', 'piko'],
                'tolerated_full_phrases': ['Hi Tikoo', 'Hi Tiko'],
                'guaranteed_recall_for_tolerated_phrases': False,
                'full_phrase_required': True, 'user_confirmed': True,
                'declared_before_revised_scoring': True,
                'source_manifest_sha256': sha(manifest),
                'protected_registry_sha256': sha(protected_path)}
    if any(policy.get(k) != v for k, v in expected.items()):
        raise ValueError('Explicit bounded user-confirmed tolerance policy required')
    protected = set(json.loads(protected_path.read_text())['audio_sha256'].values())
    rows = json.loads(manifest.read_text())
    originals = {}
    for row in rows:
        if row['split'] != 'validation' or normalized(row.get('text', '')) not in {'hitikoo', 'hitiko'}:
            continue
        if (row.get('label') != 0 or not row.get('synthetic') or
                any(row.get(k) for k in ('real_child', 'family_inputs_used', 'reference_audio_used',
                                        'evaluation_only', 'frozen_holdout', 'parent_sha256', 'ancestry_parents')) or
                row['sha256'] in protected or row.get('content_review') != 'passed' or
                row.get('pronunciation_review') != 'passed' or
                row.get('target_contract') != 'hi-piku-piko-v2' or row['sha256'] in originals):
            raise ValueError('Only unprotected previously admitted full T-name DEV originals can be neutral')
        originals[row['sha256']] = row
    if not originals or sorted(originals) != policy.get('tolerated_DEV_source_sha256'):
        raise ValueError('Tolerance source identity must be complete and bound before scoring')
    return {'revision': POLICY, 'policy_sha256': sha(path), 'originals': originals}


def partition(cases, context):
    active, tolerated = [], []
    for case in cases:
        if case['sha256'] in context['originals']:
            if case['label'] != 0:
                raise ValueError('Tolerance cannot remove a positive target or change its label')
            tolerated.append(case)
        else:
            active.append(case)
    return active, tolerated


def score(cases, context, rolling=3, threshold=.9):
    active, tolerated = partition(cases, context)
    # Deliberately keep neutral statistics outside target/negative metrics.
    metrics = policy_metrics(active, rolling, threshold)
    audit = {'policy_revision': POLICY, 'policy_sha256': context['policy_sha256'],
             'all_cases_retained': len(cases), 'active_gate_cases': len(active),
             'tolerated_cases': len(tolerated),
             'tolerated_triggered_cases': sum(bool((event_scores(c['probabilities'], rolling) >= threshold).any())
                                             for c in tolerated),
             'tolerated_are_not_positive_recall_trials': True,
             'historical_labels_and_traces_unchanged': True}
    return metrics, audit


def verify_revision(result, context):
    declared = result.get('tolerance_policy')
    expected = {'revision': context['revision'], 'policy_sha256': context['policy_sha256']} if context else None
    if declared != expected:
        raise ValueError('Revised tolerance metrics require their explicitly bound policy')
