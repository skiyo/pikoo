# SPDX-License-Identifier: Apache-2.0
import copy
import unittest
from wake_dev_content_review import reviewed_cohorts, verify_reviewed_gate
from hi_pikoo_model import policy_metrics


class ReviewedDev(unittest.TestCase):
    def inputs(self):
        cases = [{'sha256': 'first', 'label': 1, 'cohort': 'childlike:Chinese-accent:piku',
                  'probabilities': [0.]*10+[1.]*30, 'times_ms': list(range(0, 1200, 30)), 'completion_ms': 360},
                 {'sha256': 'second', 'label': 1, 'cohort': 'childlike:Chinese-accent:piko',
                  'probabilities': [0.]*10+[1.]*30, 'times_ms': list(range(0, 1200, 30)), 'completion_ms': 360}]
        review = {'scope': 'complete-original-synthetic-DEV-content-review',
                  'all_pending_questions_resolved': True, 'labels_unchanged': True, 'household_used': False,
                  'review_clip_selection_used_wake_scores': False,
                  'feedback': [{'index': 999, 'source_sha256': 'first', 'accepted': True, 'heard_variant': 'piko'},
                               {'index': 777, 'source_sha256': 'second', 'accepted': True, 'heard_variant': 'piku'}]}
        return cases, review

    def test_binds_by_waveform_not_audition_index_and_preserves_traces(self):
        cases, review = self.inputs(); before = copy.deepcopy(cases)
        actual = reviewed_cohorts(cases, review)
        self.assertEqual(cases, before)
        self.assertEqual([x['cohort'].split(':')[-1] for x in actual], ['piko', 'piku'])
        for old, new in zip(cases, actual):
            self.assertIs(old['probabilities'], new['probabilities'])
            self.assertEqual(old['completion_ms'], new['completion_ms'])
            self.assertEqual(old['label'], new['label'])

    def test_unknown_duplicate_or_negative_waveform_and_unresolved_review_rejected(self):
        cases, review = self.inputs()
        for key, value in [('source_sha256', 'unknown'), ('accepted', False)]:
            changed = copy.deepcopy(review); changed['feedback'][0][key] = value
            with self.assertRaises(ValueError): reviewed_cohorts(cases, changed)
        changed = copy.deepcopy(review); changed['feedback'].append(changed['feedback'][0])
        with self.assertRaises(ValueError): reviewed_cohorts(cases, changed)
        changed = copy.deepcopy(cases); changed[0]['label'] = 0
        with self.assertRaises(ValueError): reviewed_cohorts(changed, review)
        with self.assertRaises(ValueError): reviewed_cohorts(cases, {**review, 'all_pending_questions_resolved': False})

    def test_second_gate_recomputes_metrics_and_preserves_baseline_requirements(self):
        cases, review = self.inputs(); policy = {'rolling': 3, 'threshold': .9}
        result = {'reviewed_DEV': policy_metrics(reviewed_cohorts(cases, review), **policy),
                  'reviewed_DEV_gate_passed': True,
                  'reviewed_DEV_required_group_hits': {c['cohort']: 1 for c in cases}}
        verify_reviewed_gate(cases, cases, review, result, policy)
        changed = copy.deepcopy(cases); changed[0]['probabilities'] = [0.]*40
        with self.assertRaises(ValueError): verify_reviewed_gate(changed, cases, review, result, policy)
        result['reviewed_DEV_required_group_hits'][cases[0]['cohort']] = 0
        with self.assertRaises(ValueError): verify_reviewed_gate(cases, cases, review, result, policy)


if __name__ == '__main__': unittest.main()
