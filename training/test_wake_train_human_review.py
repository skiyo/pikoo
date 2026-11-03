# SPDX-License-Identifier: Apache-2.0
import copy
import unittest
from wake_train_human_review import BASE_METHOD, merge, validate


class HumanTrainReview(unittest.TestCase):
    def inputs(self):
        base = {'method': BASE_METHOD, 'original_manifest_sha256': 'manifest',
                'accepted_sha256': ['old'], 'quarantined_sha256': ['yes', 'unknown'],
                'household_used': False, 'DEV_used': False, 'TEST_opened': False, 'labels_changed': False}
        feedback = {'scope': 'independent-human-content-review-of-quarantined-synthetic-TRAIN-originals',
                    'original_manifest_sha256': 'manifest', 'per_record_human_listening': True,
                    'household_used': False, 'DEV_used': False, 'TEST_opened': False,
                    'selection_used_wake_scores': False, 'labels_changed': False,
                    'records': [{'source_sha256': 'yes', 'original_split': 'train', 'original_label': 1,
                                 'accepted': True, 'complete_target_phrase': True, 'accepted_names': ['piku', 'piko']},
                                {'source_sha256': 'unknown', 'original_split': 'train', 'original_label': 1, 'accepted': None}]}
        return base, feedback

    def test_only_explicitly_confirmed_original_is_restored_without_mutating_history(self):
        base, feedback = self.inputs(); before = copy.deepcopy(base)
        admission = merge(base, feedback)
        self.assertEqual(base, before)
        self.assertEqual(admission['accepted_sha256'], ['old', 'yes'])
        self.assertEqual(admission['quarantined_sha256'], ['unknown'])
        validate(admission, [{'sha256': 'yes', 'label': 1}] * 12)

    def test_private_holdout_score_selected_or_incomplete_reviews_are_rejected(self):
        base, original = self.inputs()
        for key, value in [('household_used', True), ('DEV_used', True), ('TEST_opened', True),
                           ('selection_used_wake_scores', True), ('labels_changed', True),
                           ('original_manifest_sha256', 'different')]:
            with self.assertRaises(ValueError): merge(base, {**original, key: value})
        for key, value in [('original_split', 'validation'), ('source_sha256', 'outside'),
                           ('original_label', 0), ('complete_target_phrase', False)]:
            feedback = copy.deepcopy(original); feedback['records'][0][key] = value
            with self.assertRaises(ValueError): merge(base, feedback)
        feedback = copy.deepcopy(original); feedback['records'].append(feedback['records'][0])
        with self.assertRaises(ValueError): merge(base, feedback)

    def test_unreviewed_promotions_and_feature_label_mismatches_fail(self):
        base, feedback = self.inputs(); admission = merge(base, feedback)
        with self.assertRaises(ValueError): validate(admission, [{'sha256': 'yes', 'label': 0}])
        with self.assertRaises(ValueError): validate(admission, [])
        admission['accepted_sha256'].append('unknown')
        with self.assertRaises(ValueError): validate(admission, [{'sha256': 'yes', 'label': 1}])


if __name__ == '__main__': unittest.main()
