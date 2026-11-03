# SPDX-License-Identifier: Apache-2.0
import unittest
import numpy as np
from hi_pikoo_train import example


class AugmentationClock(unittest.TestCase):
    def fixture(self):
        clean = np.pad(400*np.sin(2*np.pi*440*np.arange(9600)/16000), (3200, 4800))
        noisy = clean + np.random.default_rng(777).normal(0, 30, len(clean))
        row = {'label': 1, 'synthetic': True, 'split': 'train', 'sha256': 'tone-not-corpus',
               'synthetic_style': 'adult', 'accent': 'standard', 'pronunciation_variant': 'piku'}
        return clean, noisy, row

    def test_noise_does_not_move_word_clock_or_training_event(self):
        clean, noisy, row = self.fixture()
        x, y, w, meta = example(clean, row, np.random.default_rng(42))
        old = example(noisy, row, np.random.default_rng(42))[3]
        self.assertGreater(old['completion_ms']-meta['completion_ms'], 120)
        nx, ny, nw, fixed = example(noisy, row, np.random.default_rng(42), timing_reference=clean)
        self.assertEqual(fixed['completion_ms'], meta['completion_ms'])
        self.assertEqual(fixed['source_timing'], meta['source_timing'])
        np.testing.assert_array_equal(ny, y)
        np.testing.assert_array_equal(nw, w)
        self.assertFalse(np.array_equal(nx, x))  # Keep the noisy audio, not clean features.
        self.assertEqual(fixed['timing_reference_source'], 'clean-stretched-before-acoustic-v2')

    def test_reference_cannot_change_DEV_or_apply_another_time_transform(self):
        clean, noisy, row = self.fixture()
        for override in ({'split': 'validation'}, {'synthetic': False}, {'real_child': True},
                         {'family_inputs_used': True}, {'evaluation_only': True}, {'frozen_holdout': True}):
            with self.assertRaises(ValueError):
                example(noisy, {**row, **override}, np.random.default_rng(42), timing_reference=clean)
        with self.assertRaises(ValueError):
            example(noisy, row, np.random.default_rng(42), augment=True, timing_reference=clean)
        with self.assertRaises(ValueError):
            example(noisy, row, np.random.default_rng(42), timing_reference=clean[:-1])


if __name__ == '__main__': unittest.main()
