# SPDX-License-Identifier: Apache-2.0
import hashlib
import tempfile
import unittest
from pathlib import Path
try:
    import numpy as np
    from hi_pikoo_model import event_scores, select_policy, development_quality, selection_proxy
    from hi_pikoo_review import content_match, validate
    from hi_pikoo_train import admit, speech_endpoint, example
    from hi_pikoo_contract import relabel_for_contract, validate_contract
    from hi_pikoo_admit import decide
    from hi_pikoo_timing import timing, view
    from hi_pikoo_contrast import family, targets, balance
except ImportError:
    np = None


@unittest.skipIf(np is None, 'optional NumPy training environment required')
class HiPikooContracts(unittest.TestCase):
    def test_ctc_padding_optimization_preserves_loss_and_gradient(self):
        try:
            import tensorflow as tf
        except ImportError:
            self.skipTest('Optional TensorFlow runtime required')
        from hi_pikoo_phone_pretrain import ctc_loss
        logits=tf.Variable(np.random.default_rng(42).normal(size=(2,18,8)).astype(np.float32))
        labels=tf.constant([[3,12,1,2,3,0,0,0,0],[4,14,2,3,2,1,0,0,0]],tf.int32)
        with tf.GradientTape() as tape:
            full=tf.nn.ctc_loss(labels[:,2:],logits,labels[:,0],labels[:,1],logits_time_major=False,blank_index=0)
        full_grad=tape.gradient(full,logits)
        with tf.GradientTape() as tape:
            bounded=ctc_loss(labels,logits)
        bounded_grad=tape.gradient(bounded,logits)
        np.testing.assert_allclose(full,bounded,atol=1e-5)
        np.testing.assert_allclose(full_grad,bounded_grad,atol=1e-5)
    def test_silent_classifier_does_not_outscore_useful_unqualified_learning(self):
        p = {'label': 1, 'cohort': 'childlike:piko', 'completion_ms': 300,
             'times_ms': list(range(30, 901, 30)), 'probabilities': [.05]*30}
        n = {**p, 'label': 0, 'contrast_class': 2}
        silent = selection_proxy([p, n])['score']
        learning = {**p, 'probabilities': [.05]*10+[.75]*20}
        uncertain_negative = {**n, 'probabilities': [.2]*30}
        improved = selection_proxy([learning, uncertain_negative])
        self.assertGreater(improved['score'], silent)
        self.assertIsNone(select_policy([learning, uncertain_negative])['selected'])
    def test_phrase_contrast_keeps_near_phrases_negative_and_balances_train_only(self):
        rows = [{'label': 1, 'text': 'Hi Piko'}, {'label': 0, 'text': 'Hi Tikoo'},
                {'label': 0, 'text': 'Hi'}, {'label': 0, 'text': 'Pikoo'},
                {'label': 0, 'text': 'Hi pee'}]
        self.assertEqual([family(r) for r in rows], [1, 2, 3, 4, 5])
        info = [{'contrast_class': family(r), 'valid_steps': 30,
                 'times_ms': list(range(30, 901, 30)), 'completion_ms': 300} for r in rows]
        y, w = targets(info)
        balanced, detail = balance(y, w)
        self.assertEqual(set(np.unique(y)), set(range(6)))
        self.assertTrue(np.all(y[:, :9] == 0))
        self.assertTrue(np.all(y[:, 9:20] == np.arange(1, 6)[:, None]))
        self.assertEqual(detail['event_factors'], [1.]*5)
        self.assertGreater(float(balanced.max()), 1)
        with self.assertRaises(ValueError):
            balance(y[:1], w[:1])
    def test_only_quiet_exterior_padding_is_removed_and_internal_pause_stays(self):
        voice = np.sin(np.arange(8000)*.1)*1000
        pcm = np.concatenate([np.zeros(16000), voice, np.zeros(1600), voice, np.zeros(48000)])
        original = pcm.copy()
        trimmed, meta = view(pcm)
        np.testing.assert_array_equal(pcm, original)
        self.assertEqual(meta['view_start_sample'], 12800)
        self.assertEqual(meta['view_end_sample'], 38400)
        self.assertGreater(meta['removed_exterior_ms'], 3000)
        np.testing.assert_array_equal(trimmed[11200:12800], np.zeros(1600))
        self.assertTrue(timing(pcm)['preferred_1_to_2_seconds'])
        _, labels, _, meta = example(pcm, {'label': 1, 'sha256': 'timing-fixture',
            'synthetic': True}, np.random.default_rng(1))
        self.assertLess(meta['completion_ms'], 3000)
        self.assertGreater(labels.max(), .9)
        self.assertEqual(meta['source_timing']['raw_ms'], 5100)
    def test_endpoint_uses_signal_not_file_padding_and_preserves_the_audio(self):
        voice = np.sin(np.arange(16000)*.1)*1000
        pcm = np.pad(voice, (3200, 8000))
        self.assertEqual(speech_endpoint(pcm), 19840)
        noisy = pcm+np.random.default_rng(7).normal(0, 20, len(pcm))
        self.assertEqual(speech_endpoint(noisy), 19840)
        features, labels, weights, meta = example(pcm, {'label': 1, 'sha256': 'fixture'},
                                                np.random.default_rng(1))
        self.assertEqual(features.shape, (600, 40))
        self.assertGreater(meta['valid_steps']*30, meta['completion_ms']+300)
        self.assertGreater(labels.max(), .9)
        with self.assertRaises(ValueError):
            speech_endpoint(np.zeros(16000))

    def test_dual_pronunciation_is_an_explicit_derived_target_revision(self):
        original = {'label': 0, 'text': 'Hi, Piko!'}
        old = relabel_for_contract(original, 'hi-piku-v1')
        new = relabel_for_contract(original, 'hi-piku-piko-v2')
        self.assertEqual(original['label'], 0)
        self.assertEqual(old['label'], 0)
        self.assertEqual(new['label'], 1)
        self.assertEqual(new['original_label'], 0)
        self.assertTrue(content_match(new, 'Hi Pico!'))
        self.assertTrue(content_match(new, 'Hi, Piku!'))
        for text in ['Hi Tikoo', 'Hi', 'Piko', '你好 Pikoo', 'Hi Pikoo Hi Pikoo']:
            self.assertFalse(content_match(new, text), text)
        self.assertEqual(relabel_for_contract({'label': 0, 'text': 'Hi, Tikoo!'},
                         'hi-piku-piko-v2')['label'], 0)
        self.assertTrue(content_match({'label': 0, 'text': 'Hi, pee!'}, 'Hi P.'))
        self.assertFalse(content_match({'label': 0, 'text': 'Hi, pee!'}, 'Hi Piko'))
        self.assertTrue(content_match({'label': 0, 'text': 'Hi, Tikoo!'}, 'Hi Tico'))
        with self.assertRaises(ValueError):
            validate_contract({'target': 'hi-piku-piko-v2', 'accepted_names': ['piku'],
                               'declared_before_corpus_training': True})

    def test_name_alone_is_not_mistaken_for_full_piko_vowel_ambiguity(self):
        row = {'label': 0, 'text': 'Pikoo!', 'split': 'train',
            'source': 'OpenAI-Realtime-synthetic', 'recipe': 'literal-adult-v4',
            'transcript': 'Pikoo!', 'sha256': 'fixture'}
        feedback = {'clips': {'train-0060': {'pronunciation_piku': 'accepted'}}}
        accepted, reason = decide(row, {'transcript': 'Pico.'}, feedback)
        self.assertIsNone(reason)
        self.assertEqual(accepted['label'], 0)
        self.assertEqual(decide({**row, 'text': 'Hi, Piko!'},
                         {'transcript': 'Hi Piko'}, feedback)[1],
                         'piko-vowel-needs-explicit-per-record-review')

    def test_incomplete_repeated_wrong_vowels_never_pass_as_target(self):
        row = {'label': 1, 'text': 'Hi, Pikoo!'}
        for text in ['Hi', 'Pikoo', 'Hi, Piko', 'Hi, Tikoo',
                     'Hi, Pikoo! Hi, Pikoo!', 'Hi then Pikoo']:
            self.assertFalse(content_match(row, text), text)
        self.assertTrue(content_match(row, 'Hi, Piku!'))
        self.assertTrue(content_match(row, '嗨，批枯！'))
        self.assertTrue(content_match(row, '嗨，皮哭！'))

    def test_one_peak_is_not_a_wake_and_history_resets(self):
        self.assertLess(event_scores([0, 0, 1, 0, 0], 3).max(), .8)
        np.testing.assert_array_equal(event_scores([1, 1], 3), [0, 0])
        self.assertGreater(event_scores([1, 1, 1], 3)[-1], .9)
        np.testing.assert_array_equal(event_scores([0, 0, 0], 3), [0, 0, 0])

    def test_policy_rejects_false_wakes_even_with_perfect_target_recall(self):
        positive = {'label': 1, 'cohort': 'childlike:Chinese-accent',
            'completion_ms': 300, 'times_ms': list(range(30, 901, 30)),
            'probabilities': [0]*10+[1]*20}
        negative = {**positive, 'label': 0}
        self.assertIsNone(select_policy([positive, negative])['selected'])
        negative['probabilities'] = [0]*30
        self.assertIsNotNone(select_policy([positive, negative])['selected'])
        qualified = select_policy([positive, negative])
        negative['probabilities'] = [1]*30
        rejected = select_policy([positive, negative])
        self.assertGreater(development_quality(qualified), development_quality(rejected))

    def test_test_and_family_metadata_are_rejected_before_file_access(self):
        base = {'split': 'train', 'source': 'OpenAI-Realtime-synthetic',
            'synthetic': True, 'sha256': 'protected', 'path': 'missing.wav'}
        with tempfile.TemporaryDirectory() as d:
            for flag in ('evaluation_only', 'frozen_holdout', 'family_inputs_used', 'reference_audio_used'):
                with self.assertRaises(ValueError):
                    validate({**base, flag: True}, Path(d), set())
                with self.assertRaises(ValueError):
                    admit([{**base, flag: True}], Path(d), set())
            with self.assertRaisesRegex(ValueError, 'Sealed'):
                admit([{**base, 'split': 'test'}], Path(d), set())
            with self.assertRaisesRegex(ValueError, 'admission'):
                admit([base], Path(d), set())
            with self.assertRaises(ValueError):
                validate(base, Path(d), {'protected'})

    def test_requested_child_voice_cannot_be_counted_as_perceived_child(self):
        row = {'split': 'train', 'source': 'OpenAI-Realtime-synthetic',
            'synthetic': True, 'admitted_to_training': True,
            'content_review': 'passed', 'pronunciation_review': 'passed',
            'synthetic_style': 'childlike', 'perceived_style': 'adult',
            'perceived_style_review': 'passed'}
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, 'reviewed perceived style'):
                admit([row], Path(d), set())


if __name__ == '__main__':
    unittest.main()
