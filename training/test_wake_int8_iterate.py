# SPDX-License-Identifier: Apache-2.0
import unittest
import json
from pathlib import Path
import tempfile
try:
    from wake_int8_iterate import qualification, balance_train_weights, balance_positive_cohorts, load_profiles, optimizer_spec, set_encoder_trainability, validate_natural_append_options
    import numpy as np
except ImportError:
    qualification = None


@unittest.skipIf(qualification is None, 'Optional pinned training runtime required')
class Int8Qualification(unittest.TestCase):
    def test_public_phone_encoder_can_be_frozen_without_changing_the_head(self):
        from types import SimpleNamespace
        class Norm:
            trainable = True
        conv, norm, head = SimpleNamespace(trainable=True), Norm(), SimpleNamespace(trainable=True)
        encoder = SimpleNamespace(layers=[conv, norm])
        set_encoder_trainability(encoder, Norm, frozen=False)
        self.assertTrue(conv.trainable)
        self.assertFalse(norm.trainable)
        result = set_encoder_trainability(encoder, Norm, frozen=True)
        self.assertEqual(result['encoder_trainable_layers'], 0)
        self.assertFalse(conv.trainable)
        self.assertTrue(head.trainable)

    def test_encoder_freeze_is_explicit_and_phone_initialization_only(self):
        profile = {'name': 'phone', 'channels': 96, 'head': 64, 'context_steps': 72,
                   'initialization': 'phone-encoder', 'learning_rate': .0005, 'max_epochs': 30,
                   'seeds': [42, 43], 'encoder_frozen': True}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'profiles.json'; path.write_text(json.dumps([profile]))
            self.assertTrue(load_profiles(path)[0]['encoder_frozen'])
            for update in ({'encoder_frozen': 'yes'}, {'initialization': 'fresh'}):
                path.write_text(json.dumps([{**profile, **update}]))
                with self.assertRaises(ValueError): load_profiles(path)

    def test_regularization_is_bounded_and_legacy_Adam_is_unchanged(self):
        profile = {'learning_rate': .0005}
        self.assertEqual(optimizer_spec(profile), ('Adam', {'learning_rate': .0005}))
        name, options = optimizer_spec({**profile, 'weight_decay': .01}, clipnorm=True)
        self.assertEqual(name, 'AdamW')
        self.assertEqual(options, {'learning_rate': .0005, 'weight_decay': .01, 'global_clipnorm': 1.})
        for value in (-.01, .001, .1, float('nan'), float('inf')):
            with self.assertRaises(ValueError): optimizer_spec({**profile, 'weight_decay': value})
        bounded = {**profile, 'name': 'regularized', 'channels': 96, 'head': 64,
                   'initialization': 'fresh', 'max_epochs': 30, 'seeds': [42, 43], 'weight_decay': .01}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'profiles.json'; path.write_text(json.dumps([bounded]))
            self.assertEqual(load_profiles(path)[0]['weight_decay'], .01)
            bounded['weight_decay'] = .1; path.write_text(json.dumps([bounded]))
            with self.assertRaises(ValueError): load_profiles(path)

    def test_auxiliary_weight_is_a_bounded_predeclared_training_choice(self):
        profile = {'name': 'auxiliary', 'channels': 48, 'head': 64, 'context_steps': 20,
                   'initialization': 'fresh', 'learning_rate': .0001, 'max_epochs': 20,
                   'seeds': [42, 43], 'auxiliary_phrase_weight': .2}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'profiles.json'; path.write_text(json.dumps([profile]))
            self.assertEqual(load_profiles(path)[0]['auxiliary_phrase_weight'], .2)
            profile['auxiliary_phrase_weight'] = 5
            path.write_text(json.dumps([profile]))
            with self.assertRaises(ValueError): load_profiles(path)

    def test_cohort_weighting_changes_only_positive_train_events(self):
        labels = np.tile([[1., 0., 0.]], (6, 1))
        weights = np.asarray([[w, 2., 3.] for w in (2, 3, 4, 5, 6, 7)], np.float32)
        metadata = [{'label': 1, 'cohort': str(i)} for i in range(6)]
        result, proof = balance_positive_cohorts(labels, weights, metadata)
        np.testing.assert_allclose(result[:, 0], np.full(6, 4.5))
        np.testing.assert_array_equal(result[:, 1:], weights[:, 1:])
        self.assertEqual(len(proof['factors']), 6)
        with self.assertRaises(ValueError):
            balance_positive_cohorts(labels, weights, metadata[:2])
    def test_reviewed_union_vowel_sources_do_not_invent_or_replace_known_cohorts(self):
        labels = np.tile([[1., 0., 0.]], (7, 1))
        weights = np.asarray([[w, 2., 3.] for w in (2, 3, 4, 5, 6, 7, 9)], np.float32)
        metadata = [{'label': 1, 'cohort': str(i)} for i in range(6)]
        metadata.append({'label': 1, 'cohort': 'childlike:unverified:piku-or-piko-human-accepted',
                         'sha256': 'approved-original', 'source': 'Qwen3-TTS-hi-piku-synthetic-local'})
        result, proof = balance_positive_cohorts(labels, weights, metadata, ['approved-original'])
        np.testing.assert_allclose(result[:6, 0], np.full(6, 4.5))
        np.testing.assert_array_equal(result[6], weights[6])
        np.testing.assert_array_equal(result[:, 1:], weights[:, 1:])
        self.assertEqual(proof['supplemental_unresolved_cohort_positive_examples'], 1)
        self.assertEqual(proof['supplemental_unresolved_cohort_event_mass'], 9.)
        self.assertEqual(len(proof['factors']), 6)
        with self.assertRaises(ValueError): balance_positive_cohorts(labels, weights, metadata)
        with self.assertRaises(ValueError):
            balance_positive_cohorts(labels, weights, metadata, ['different-original'])
        with self.assertRaisesRegex(ValueError, 'six declared'):
            balance_positive_cohorts(labels[1:], weights[1:], metadata[1:], ['approved-original'])
        changed = [*metadata[:-1], {**metadata[-1], 'source': 'unknown'}]
        with self.assertRaises(ValueError):
            balance_positive_cohorts(labels, weights, changed, ['approved-original'])

    def test_train_balance_does_not_mutate_original_cache_or_use_dev(self):
        labels = np.asarray([[1., 0., 0., 0.]])
        weights = np.asarray([[1., 4., 4., 4.]], np.float32)
        balanced, proof = balance_train_weights(labels, weights)
        np.testing.assert_array_equal(weights, [[1., 4., 4., 4.]])
        self.assertEqual(proof['positive_factor'], 4.)
        self.assertAlmostEqual(float(balanced[labels < .5].sum()/balanced[labels > .5].sum()), 3.)
        with self.assertRaises(ValueError):
            balance_train_weights(np.zeros_like(labels), weights)

    def test_adult_union_sources_remain_separate_from_the_six_required_cohorts(self):
        labels = np.tile([[1., 0.]], (7, 1))
        weights = np.ones_like(labels)
        metadata = [{'label': 1, 'cohort': str(i)} for i in range(6)]
        extra = {'label': 1, 'cohort': 'adult:unverified:piku-or-piko-human-accepted',
                 'sha256': 'reviewed', 'source': 'Qwen3-TTS-hi-piku-synthetic-local'}
        _, proof = balance_positive_cohorts(labels, weights, [*metadata, extra], ['reviewed'])
        self.assertEqual(proof['supplemental_unresolved_cohort_positive_examples'], 1)
        with self.assertRaises(ValueError):
            balance_positive_cohorts(labels, weights, [*metadata, extra])
        with self.assertRaisesRegex(ValueError, 'six declared'):
            balance_positive_cohorts(labels, weights, [*metadata, {**extra,
                'cohort': 'unverified:unverified:piku-or-piko-human-accepted'}], ['reviewed'])

    def test_late_natural_append_options_fail_before_preparation_when_incomplete(self):
        from types import SimpleNamespace
        config = dict(natural_train_manifest=None, natural_train_review=None, tempo_config='tempo',
                      base_admitted_manifest='base', train_admission='admission', cohort_meta='meta',
                      phrase_events='events')
        validate_natural_append_options(SimpleNamespace(**config))
        with self.assertRaises(ValueError):
            validate_natural_append_options(SimpleNamespace(**{**config, 'natural_train_review': 'review'}))
        complete = {**config, 'natural_train_manifest': 'natural', 'natural_train_review': 'review'}
        validate_natural_append_options(SimpleNamespace(**complete))
        for key in ('tempo_config', 'base_admitted_manifest', 'train_admission', 'cohort_meta', 'phrase_events'):
            with self.assertRaises(ValueError):
                validate_natural_append_options(SimpleNamespace(**{**complete, key: None}))
    @staticmethod
    def metrics(hits, passed):
        return {'groups': {'adult': {'targets': 20, 'hits': 19},
                           'childlike': {'targets': 20, 'hits': hits}},
                'false_wakes': 0, 'early_wakes': 0, 'passed': passed}

    def test_preserving_an_unqualified_baseline_is_not_qualification(self):
        old = self.metrics(16, False)
        result = qualification(old, 0, old)
        self.assertFalse(result['qualified'])
        self.assertTrue(result['old_DEV_preserved'])
        self.assertEqual(result['required_group_hits']['childlike'], 18)
        self.assertEqual(result['positive_shortfall'], 2)

    def test_full_goal_and_new_negative_limit_are_both_required(self):
        baseline = self.metrics(16, False)
        good = self.metrics(18, True)
        self.assertTrue(qualification(good, 0, baseline)['qualified'])
        self.assertFalse(qualification(good, 1, baseline)['qualified'])
        self.assertFalse(qualification(good, 2, baseline)['qualified'])
        regressed = {**good, 'early_wakes': 1, 'passed': False}
        self.assertFalse(qualification(regressed, 0, baseline)['qualified'])

    def test_silent_classifier_cannot_win_by_rejecting_everything(self):
        baseline = self.metrics(16, False)
        quiet = self.metrics(0, False)
        self.assertLess(qualification(quiet, 0, baseline)['selection_score'],
                        qualification(baseline, 6, baseline)['selection_score'])


if __name__ == '__main__':
    unittest.main()
