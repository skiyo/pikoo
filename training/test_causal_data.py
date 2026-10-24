import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from causal_data import training_rows, frame_targets, example


class CausalDataTest(unittest.TestCase):
    def test_group_and_hash_guards_do_not_decode_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'train.wav').write_bytes(b'fixture')
            digest = hashlib.sha256(b'fixture').hexdigest()
            train = dict(path='train.wav', sha256=digest, group='train', split='train', label=0)
            validation = dict(path='must-not-read.wav', sha256='different', group='validation', split='validation', label=1)
            self.assertEqual(training_rows([train, validation], root, set()), [train])
            with self.assertRaisesRegex(ValueError, 'Protected'):
                training_rows([train], root, {digest})
            with self.assertRaisesRegex(ValueError, 'leaks'):
                training_rows([train, dict(validation, group='train')], root, set())
            with self.assertRaisesRegex(ValueError, 'leaks'):
                training_rows([train, dict(validation, sha256=digest)], root, set())
            for flag in ('evaluation_only', 'frozen_holdout'):
                with self.assertRaisesRegex(ValueError, 'Protected'):
                    training_rows([dict(train, **{flag: True})], root, set())

    def test_last_consumed_timestamp_and_normalized_padding_mask(self):
        ends = np.arange(1, 11)*160
        labels, weights = frame_targets(ends, 900, 1, 15)
        np.testing.assert_array_equal(labels, [0, 1, 1, 0, 0])
        np.testing.assert_allclose(weights, [5/3, 5/3, 5/3, 0, 0])
        labels, _ = frame_targets(ends, 900, 3, 15)
        np.testing.assert_array_equal(labels, [0, 3, 3, 0, 0])
        for broken in ([160, 160], [320, 160]):
            with self.assertRaises(ValueError):
                frame_targets(broken, 100, 1, 15)
        with self.assertRaises(ValueError):
            frame_targets(ends, 900, 1, 9)

    def test_no_partial_positive_and_annotation_drops_following_sentence(self):
        row = dict(split='train', label=1, wake_end_sample=16000, text='你好Pikoo')
        # A recognizable marker in the following sentence must never survive.
        pcm = np.concatenate([np.ones(16000), np.full(16000, 30000)])
        seen = []
        def frontend(wave):
            seen.append(wave.copy())
            count = len(wave)//160-2
            return np.zeros((count, 40), np.float32), np.arange(3, count+3)*160
        with patch('causal_data.timestamped_features', side_effect=frontend):
            _, labels, weights, info = example(pcm, row, np.random.default_rng(18))
        self.assertLess(np.max(abs(seen[0])), 1000)
        valid = np.flatnonzero(weights)
        target = np.flatnonzero(labels == 1)
        self.assertGreaterEqual(len(target), 5)
        self.assertLess(target[0], valid[-1])
        self.assertTrue(info['full_phrase_retained'])
        for flag in ('evaluation_only', 'frozen_holdout'):
            with self.assertRaises(ValueError):
                example(pcm, dict(row, **{flag: True}), np.random.default_rng(18))
        with self.assertRaisesRegex(ValueError, 'exceeds'):
            example(np.ones(100000), dict(row, wake_end_sample=100000), np.random.default_rng(18))
        with patch('causal_data.timestamped_features', side_effect=frontend):
            _, labels, _, info = example(np.ones(96000),
                dict(split='train', label=0, text='你好皮皮'), np.random.default_rng(18))
        self.assertFalse(info['full_phrase_retained'])
        self.assertEqual(info['complete_class'], 0)
        self.assertFalse(np.any(labels))


if __name__ == '__main__':
    unittest.main()
