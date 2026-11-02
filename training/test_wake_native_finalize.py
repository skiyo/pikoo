# SPDX-License-Identifier: Apache-2.0
import copy
import unittest
from wake_native_finalize import validate_gate, base_representatives


class NativeFinalize(unittest.TestCase):
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
            'qualified': True, 'old_DEV_preserved': True, 'backend': 'pinned native TFLite Micro',
            'household_used': False, 'TEST_opened': False, 'new_negative_DEV_cases': 261,
            'new_negative_DEV_false_clips': 0,
            'required_group_hits': {'adult:standard:piku': 26, 'adult:standard:piko': 3,
                'adult:Chinese-accent:piku': 26, 'adult:Chinese-accent:piko': 10,
                'childlike:Chinese-accent:piku': 11, 'childlike:Chinese-accent:piko': 12},
            'old_DEV': {'passed': True, 'false_wakes': 0, 'early_wakes': 0, 'latency_p95_ms': 100,
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
