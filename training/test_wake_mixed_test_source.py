# SPDX-License-Identifier: Apache-2.0
import copy
import unittest
from wake_mixed_test import COHORTS, protocol
from wake_mixed_test_source import source_plan


class MixedSourcePlan(unittest.TestCase):
    def setUp(self):
        self.policy = {'target': 'hi-piku-piko-v2', 'development_passed': True,
            'source_native_freeze_sha256': 'native-fixture', 'micro_proof_sha256': 'parity-fixture',
            'required_test_cohorts': COHORTS, 'required_fresh_test_speakers': ['openai:echo', 'openai:shimmer'],
            'model_sha256': 'model-fixture', 'candidate_frozen_at': '2026-11-03T01:00:00+00:00',
            'rolling': 3, 'threshold': .9}
        self.plan = protocol(self.policy, 'policy-sha', 'protected-sha', '2026-11-03T02:00:00+00:00')

    def test_only_70_declared_adult_sources_not_family_or_child_impersonation(self):
        rows = source_plan(self.plan, self.policy, 'a'*64)
        self.assertEqual(len(rows), 70)
        self.assertEqual(sum(r['label'] for r in rows), 40)
        self.assertEqual(len({r['id'] for r in rows}), 70)
        self.assertEqual({r['speaker'] for r in rows}, {'openai:echo', 'openai:shimmer'})
        for row in rows:
            self.assertEqual(row['role'], 'adult')
            self.assertIsNone(row['actual_variant'])
            self.assertIsNone(row['actual_age'])
            self.assertFalse(row['model_scored'])
            self.assertFalse(row['training_or_tuning_allowed'])
            self.assertFalse(row['family_inputs_used'])
            self.assertTrue(row['evaluation_only'])
            self.assertTrue(row['request_id'].startswith('mixed-aaaaaaaaaaaa-TEST-'))

    def test_missing_family_plan_or_lower_policy_cannot_unlock_adult_only_billing(self):
        for mutate in ('drop-family', 'threshold', 'replace-child-with-adult'):
            plan = copy.deepcopy(self.plan)
            if mutate == 'drop-family': plan['slots'] = [s for s in plan['slots'] if s['source_kind'] == 'synthetic']
            if mutate == 'threshold': plan['fixed_policy']['threshold'] = .85
            if mutate == 'replace-child-with-adult':
                next(s for s in plan['slots'] if s['role'] == 'child')['role'] = 'adult'
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                source_plan(plan, self.policy, 'a'*64)

    def test_both_target_vowels_and_all_six_negative_categories_are_predeclared(self):
        rows = source_plan(self.plan, self.policy, 'a'*64)
        self.assertEqual(sum(r['text']=='Hi, Pee Koo!' for r in rows), 20)
        self.assertEqual(sum(r['text']=='Hi, Pico!' for r in rows), 20)
        negatives = [r for r in rows if not r['label']]
        self.assertEqual(len({r['negative_category'] for r in negatives}), 6)
        for r in negatives:
            self.assertIsNone(r['intended_cohort'])
            self.assertEqual(r['content_review'], 'pending')
        self.assertTrue(any(r['text']=='Hi, Tee Koo!' for r in negatives))


if __name__ == '__main__': unittest.main()
