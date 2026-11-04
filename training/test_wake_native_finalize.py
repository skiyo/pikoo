# SPDX-License-Identifier: Apache-2.0
import copy
import unittest
from unittest.mock import patch
from wake_native_finalize import validate_gate, base_representatives, verify_saved_dev, verify_tempo, secondary_spec
from hi_pikoo_model import GRID, policy_metrics


class NativeFinalize(unittest.TestCase):
    def test_required_secondary_guard_cannot_be_skipped_by_missing_candidate_profile(self):
        spec = {'source_manifest_sha256': 'manifest'}
        plan = {'profiles': [{'name': 'candidate', 'required_secondary_negative_dev': spec}]}
        self.assertEqual(secondary_spec(plan, {'profile': 'candidate'}), spec)
        for result in ({}, {'profile': 'other'}):
            with self.assertRaises(ValueError): secondary_spec(plan, result)
        self.assertIsNone(secondary_spec({}, {}))

    def test_appended_sources_are_not_mistaken_for_retained_cached_fixture_indices(self):
        plan = {'retained_original_TRAIN_indices': [0, 2, 4, 5],
                'TRAIN_effective_examples': 6, 'representative_TRAIN_indices': [1, 3, 4, 5]}
        self.assertEqual(base_representatives(plan, 6), [2, 5])
        with self.assertRaises(ValueError):
            base_representatives({**plan, 'representative_TRAIN_indices': [-1]}, 6)
        with self.assertRaises(ValueError):
            base_representatives({**plan, 'representative_TRAIN_indices': [6]}, 6)

    def inputs(self):
        groups = {'adult:standard:piku': 28, 'adult:standard:piko': 3,
                  'adult:Chinese-accent:piku': 27, 'adult:Chinese-accent:piko': 10,
                  'childlike:Chinese-accent:piku': 11, 'childlike:Chinese-accent:piko': 13}
        frozen = {'policy': {'rolling': 3, 'threshold': .9}, 'evaluation': {
            'rolling': 3, 'threshold': .9,
            'qualified': True, 'old_DEV_preserved': True, 'backend': 'pinned native TFLite Micro',
            'household_used': False, 'TEST_opened': False, 'new_negative_DEV_cases': 261,
            'new_negative_DEV_false_clips': 0,
            'required_group_hits': {'adult:standard:piku': 26, 'adult:standard:piko': 3,
                'adult:Chinese-accent:piku': 26, 'adult:Chinese-accent:piko': 10,
                'childlike:Chinese-accent:piku': 11, 'childlike:Chinese-accent:piko': 12},
            'old_DEV': {'rolling': 3, 'threshold': .9,
                        'passed': True, 'false_wakes': 0, 'early_wakes': 0, 'latency_p95_ms': 100,
                        'groups': {g: {'hits': n, 'targets': n} for g, n in groups.items()}}}}
        review = {'scope': 'complete-original-synthetic-DEV-content-review',
                  'original_manifest_sha256': 'manifest', 'all_pending_questions_resolved': True,
                  'labels_unchanged': True, 'household_used': False,
                  'review_clip_selection_used_wake_scores': False,
                  'reviewed_uncertainty_indices': [10, 21, 40, 57, 58, 60, 72]}
        return frozen, review

    def test_numeric_native_gate_and_complete_independent_content_review(self):
        frozen, review = self.inputs()
        self.assertIs(validate_gate(frozen, review, 'manifest'), frozen['evaluation'])

    def test_revised_scope_requires_bound_policy_and_never_silently_passes_legacy_gate(self):
        frozen, review = self.inputs()
        context = {'revision': 'explicit-tolerance', 'policy_sha256': 'policy'}
        frozen['evaluation']['tolerance_policy'] = context.copy()
        with self.assertRaises(ValueError): validate_gate(frozen, review, 'manifest')
        self.assertIs(validate_gate(frozen, review, 'manifest', context), frozen['evaluation'])
        with self.assertRaises(ValueError):
            validate_gate(frozen, review, 'manifest', {**context, 'policy_sha256': 'different'})

    def test_stronger_current_candidate_floor_is_allowed_but_weaker_floor_is_not(self):
        frozen, review = self.inputs()
        frozen['evaluation']['required_group_hits']['adult:standard:piku'] = 28
        self.assertIs(validate_gate(frozen, review, 'manifest'), frozen['evaluation'])
        frozen['evaluation']['required_group_hits']['adult:standard:piku'] = 25
        with self.assertRaises(ValueError): validate_gate(frozen, review, 'manifest')

    def test_tempo_gate_requires_all_saved_cases_and_recomputes_probabilities(self):
        frozen, review = self.inputs(); review = {**review, 'feedback': []}
        base = [{'label': 0, 'probabilities': [0.]*40} for _ in range(52)]
        for group, record in frozen['evaluation']['old_DEV']['groups'].items():
            base.extend({'label': 1, 'cohort': group, 'probabilities': [0.]*10+[1.]*30}
                        for _ in range(record['targets']))
        cases = [{**c, 'sha256': str(i), 'valid_steps': 40, 'completion_ms': 360,
                  'times_ms': list(range(0, 1200, 30)), 'cohort': c.get('cohort', 'ordinary'),
                  'tempo_factor': factor} for i, c in enumerate(base) for factor in (1.15, 1.3, 1.5)]
        metadata = [{k: v for k, v in c.items() if k != 'probabilities'} for c in cases]
        result = {'qualified': True, 'fixed_policy': {'rolling': 3, 'threshold': .9}, 'factors': []}
        for factor in (1.15, 1.3, 1.5):
            metrics = policy_metrics([c for c in cases if c['tempo_factor'] == factor], 3, .9)
            result['factors'].append({'factor': factor, 'historical_groups': metrics, 'reviewed_groups': metrics,
                                     'positive_shortfall': 0, 'qualified': True})
        verify_tempo(cases, metadata, result, review)
        with self.assertRaises(ValueError): verify_tempo(cases[:-1], metadata[:-1], result, review)
        changed = copy.deepcopy(cases); changed[0]['probabilities'] = [1.]*40
        with self.assertRaises(ValueError): verify_tempo(changed, metadata, result, review)
        from wake_tolerated_confusables import score
        tolerance = {'originals': {'0': {}}, 'policy_sha256': 'policy'}
        revised = copy.deepcopy(cases)
        for case in revised:
            if case['sha256'] == '0': case['probabilities'] = [1.]*40
        revised_result = {'qualified': True, 'fixed_policy': result['fixed_policy'], 'factors': []}
        for factor in (1.15, 1.3, 1.5):
            metrics, audit = score([c for c in revised if c['tempo_factor'] == factor], tolerance)
            revised_result['factors'].append({'factor':factor, 'historical_groups':metrics,
                'reviewed_groups':metrics, 'tolerance_audit':audit, 'positive_shortfall':0, 'qualified':True})
        verify_tempo(revised, metadata, revised_result, review, tolerance)
        with self.assertRaises(ValueError): verify_tempo(revised, metadata, revised_result, review)
        # Ordinary speech remains a hard failure under the revised policy.
        bad = copy.deepcopy(revised); bad[3]['probabilities'] = [1.]*40
        with self.assertRaises(ValueError): verify_tempo(bad, metadata, revised_result, review, tolerance)

    def test_original_grid_requires_matching_policy_evidence(self):
        for rolling, threshold in GRID:
            frozen, review = self.inputs()
            policy = {'rolling': rolling, 'threshold': threshold}
            frozen['policy'] = policy
            frozen['evaluation'].update(policy)
            frozen['evaluation']['old_DEV'].update(policy)
            self.assertIs(validate_gate(frozen, review, 'manifest'), frozen['evaluation'])
        for rolling, threshold in [(1, .9), (3, .7), (5, .91)]:
            frozen, review = self.inputs()
            frozen['policy'] = {'rolling': rolling, 'threshold': threshold}
            with self.assertRaises(ValueError): validate_gate(frozen, review, 'manifest')
        for field in ('rolling', 'threshold'):
            frozen, review = self.inputs()
            frozen['evaluation'][field] = 5 if field == 'rolling' else .85
            with self.assertRaises(ValueError): validate_gate(frozen, review, 'manifest')
        frozen, review = self.inputs()
        frozen['evaluation']['old_DEV']['rolling'] = 5
        with self.assertRaises(ValueError): validate_gate(frozen, review, 'manifest')

    def test_negative_summaries_cannot_silently_reuse_another_policy(self):
        frozen, _ = self.inputs()
        policy, result = frozen['policy'], frozen['evaluation']
        cases = [{'label': i >= 52} for i in range(144)]
        negatives = [{'peak': .2, 'activated': False} for _ in range(261)]
        with patch('wake_native_finalize.policy_metrics', return_value=result['old_DEV']):
            verify_saved_dev(cases, negatives, result, policy, policy)
            for plan in ({'rolling': 5, 'threshold': .9}, {'rolling': 3, 'threshold': .85}):
                with self.assertRaises(ValueError): verify_saved_dev(cases, negatives, result, policy, plan)
            for peak, activated in [(.91, False), (.2, True), (float('nan'), False),
                                    (float('inf'), False), (-.1, False), (1.1, False)]:
                changed = [dict(n) for n in negatives]
                changed[0].update(peak=peak, activated=activated)
                with self.assertRaises(ValueError): verify_saved_dev(cases, changed, result, policy, policy)
            changed = [dict(n) for n in negatives]
            changed[0].update(peak=.91, activated=True)
            with self.assertRaises(ValueError): verify_saved_dev(cases, changed, result, policy, policy)

    def test_saved_trace_metrics_are_recomputed_under_selected_policy(self):
        frozen, _ = self.inputs()
        groups = frozen['evaluation']['old_DEV']['groups']
        cases = [{'label': 0, 'probabilities': [0.] * 40,
                  'times_ms': list(range(0, 1200, 30))} for _ in range(52)]
        for cohort, group in groups.items():
            cases.extend({'label': 1, 'cohort': cohort, 'probabilities': [0.] * 10 + [1.] * 30,
                          'times_ms': list(range(0, 1200, 30)), 'completion_ms': 360}
                         for _ in range(group['targets']))
        negatives = [{'peak': .2, 'activated': False} for _ in range(261)]
        policy = {'rolling': 5, 'threshold': .85}
        result = {**frozen['evaluation'], **policy, 'old_DEV': policy_metrics(cases, **policy)}
        self.assertTrue(result['old_DEV']['passed'])
        verify_saved_dev(cases, negatives, result, policy, policy)
        result['old_DEV']['groups']['adult:standard:piku']['hits'] -= 1
        with self.assertRaises(ValueError): verify_saved_dev(cases, negatives, result, policy, policy)

    def test_a_claimed_pass_does_not_bypass_any_hard_gate(self):
        original, review = self.inputs()
        for key, value in [('new_negative_DEV_false_clips', 1), ('new_negative_DEV_cases', 260),
                           ('household_used', True), ('TEST_opened', True), ('backend', 'float')]:
            f = copy.deepcopy(original); f['evaluation'][key] = value
            with self.assertRaises(ValueError): validate_gate(f, review, 'manifest')
        for key, value in [('false_wakes', 1), ('early_wakes', 1), ('latency_p95_ms', 801),
                           ('latency_p95_ms', float('nan'))]:
            f = copy.deepcopy(original); f['evaluation']['old_DEV'][key] = value
            with self.assertRaises(ValueError): validate_gate(f, review, 'manifest')
        f = copy.deepcopy(original)
        f['evaluation']['old_DEV']['groups']['childlike:Chinese-accent:piko']['hits'] = 11
        with self.assertRaises(ValueError): validate_gate(f, review, 'manifest')

    def test_unresolved_changed_or_score_selected_labels_do_not_open_test(self):
        frozen, original = self.inputs()
        for key, value in [('all_pending_questions_resolved', False), ('labels_unchanged', False),
                           ('household_used', True), ('review_clip_selection_used_wake_scores', True),
                           ('reviewed_uncertainty_indices', [10, 40, 57, 58])]:
            review = dict(original); review[key] = value
            with self.assertRaises(ValueError): validate_gate(frozen, review, 'manifest')
        with self.assertRaises(ValueError): validate_gate(frozen, original, 'other-manifest')


if __name__ == '__main__': unittest.main()
