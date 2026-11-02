# SPDX-License-Identifier: Apache-2.0
"""Overlay heard vowels by original audio hash, never by audition order.

Keep historical cohorts and scores intact. This adds a second DEV gate; it
does not delete cases, change target labels, endpoints or probability traces.
Unreviewed vowels remain historical metadata, not phonetic gold.
"""
def reviewed_cohorts(cases, review):
    if (review.get('scope') != 'complete-original-synthetic-DEV-content-review' or
            review.get('all_pending_questions_resolved') is not True or
            review.get('labels_unchanged') is not True or review.get('household_used') is not False or
            review.get('review_clip_selection_used_wake_scores') is not False):
        raise ValueError('Independent complete content review required')
    hashes = {c['sha256'] for c in cases}
    corrections = {}
    for record in review['feedback']:
        variant = record.get('heard_variant')
        if variant not in {'piku', 'piko'}:
            continue
        digest = record.get('source_sha256')
        if record.get('accepted') is not True or digest not in hashes or digest in corrections:
            raise ValueError('Reviewed vowel must bind to one original DEV waveform')
        corrections[digest] = variant
    result = []
    for case in cases:
        row = dict(case)
        if case['sha256'] in corrections:
            if not case['label']:
                raise ValueError('Vowel review cannot turn a negative into a target')
            row['cohort'] = case['cohort'].rsplit(':', 1)[0]+':'+corrections[case['sha256']]
        result.append(row)
    return result


def verify_reviewed_gate(cases, baseline_cases, review, result, policy):
    import math
    from hi_pikoo_model import policy_metrics
    actual = policy_metrics(reviewed_cohorts(cases, review), **policy)
    baseline = policy_metrics(reviewed_cohorts(baseline_cases, review), 3, .9)
    required = {g: max(v['hits'], math.ceil(.9*v['targets'])) for g, v in baseline['groups'].items()}
    if (actual != result.get('reviewed_DEV') or not actual['passed'] or
            result.get('reviewed_DEV_gate_passed') is not True or
            required != result.get('reviewed_DEV_required_group_hits') or
            any(actual['groups'][g]['hits'] < n for g, n in required.items())):
        raise ValueError('Human-reviewed grouping gate is not proved by original native traces')
