# SPDX-License-Identifier: Apache-2.0
import unittest
import numpy as np
from wake_phrase_auxiliary import training_targets
from wake_train_events import verify_example


class PhraseAuxiliary(unittest.TestCase):
    def test_auxiliary_gradient_shares_binary_features_without_exporting_head(self):
        try:
            import tensorflow as tf
        except ImportError:
            self.skipTest('Optional TensorFlow training runtime required')
        from wake_phrase_auxiliary import attach
        from hi_pikoo_model import sequence_loss
        tf.keras.utils.set_random_seed(42)
        features = tf.keras.Input((6, 1, 4))
        hidden = tf.keras.layers.Conv2D(4, 1, activation='relu')(features)
        scalar = tf.keras.layers.Conv2D(1, 1, activation='sigmoid', name='wake_probability')(hidden)
        binary = tf.keras.Model(features, tf.keras.layers.Reshape((6,))(scalar))
        training = attach(binary)
        training.compile(optimizer=tf.keras.optimizers.SGD(.01),
            loss={'wake': sequence_loss, 'phrase': 'sparse_categorical_crossentropy'},
            loss_weights={'wake': 1., 'phrase': .2})
        data = np.ones((2, 6, 1, 4), np.float32)
        before = [v.copy() for v in binary.get_weights()]
        training.train_on_batch(data,
            {'wake': np.ones((2, 6)), 'phrase': np.ones((2, 6), np.int32)},
            sample_weight={'wake': np.ones((2, 6)), 'phrase': np.full((2, 6), 2.)})
        self.assertTrue(any(not np.array_equal(a, b) for a, b in zip(before, binary.get_weights())))
        self.assertEqual(tuple(binary(data).shape), (2, 6))
        self.assertFalse(any('auxiliary_phrase' in layer.name for layer in binary.layers))

    def archive(self):
        return {'proof': {'every_original_TRAIN_array_byte_equal': True,
            'household_used': False, 'DEV_waveforms_read': False, 'TEST_opened': False,
            'source_manifest_labels_unchanged': True},
            'records': [{'label': int(c == 1), 'contrast_class': c, 'valid_steps': 8,
                         'times_ms': [30*i for i in range(1, 9)], 'completion_ms': 150}
                        for c in range(1, 6)]}

    def test_all_competitor_families_remain_distinct_and_padding_masked(self):
        archive = self.archive()
        labels = np.zeros((6, 10), np.float32); labels[0, 4:8] = 1
        weights = np.zeros_like(labels); weights[:, :8] = 1
        saved = labels.copy(), weights.copy()
        y, w, summary = training_targets(archive, labels, weights)
        for i in range(5):
            self.assertEqual(y[i, 4], i+1)
        self.assertFalse(y[5].any())
        self.assertFalse(w[:, 8:].any())
        np.testing.assert_array_equal(labels, saved[0]); np.testing.assert_array_equal(weights, saved[1])
        self.assertEqual(len(summary['event_factors']), 5)

    def test_unverified_or_protected_metadata_cannot_supply_targets(self):
        labels = np.zeros((5, 10)); labels[0, 4] = 1
        for key in ('household_used', 'DEV_waveforms_read', 'TEST_opened'):
            archive = self.archive(); archive['proof'][key] = True
            with self.assertRaises(ValueError): training_targets(archive, labels, np.ones_like(labels))
        archive = self.archive(); archive['records'][1]['label'] = 1
        with self.assertRaises(ValueError): training_targets(archive, labels, np.ones_like(labels))

    def test_recovery_requires_exact_features_labels_and_weights(self):
        original = (np.zeros((3, 40)), np.array([1.]), np.array([2.]))
        verify_example(original, original, 0)
        for index in range(3):
            changed = [v.copy() for v in original]; changed[index].flat[0] += 1
            with self.assertRaises(ValueError): verify_example(original, changed, 0)
        changed = [v.astype(np.float32) for v in original]
        with self.assertRaises(ValueError): verify_example(original, changed, 0)


if __name__ == '__main__': unittest.main()
