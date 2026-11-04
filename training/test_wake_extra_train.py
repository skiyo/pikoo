# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch
import numpy as np
from wake_extra_train import complete_base_metadata, natural_example


class ExtraTrainMetadata(unittest.TestCase):
    def test_natural_new_original_never_uses_legacy_resampling_and_keeps_clean_clock(self):
        pcm = 5000*np.sin(2*np.pi*440*np.arange(32000)/16000).astype(np.float32)
        original = pcm.copy()
        with patch('wake_extra_train.example', return_value='fixture') as builder:
            self.assertEqual(natural_example(pcm, {}, np.random.default_rng(42), 0), 'fixture')
            args, kwargs = builder.call_args
            np.testing.assert_array_equal(args[0], pcm)
            self.assertEqual(kwargs, {'augment': False})
            self.assertEqual(natural_example(pcm, {}, np.random.default_rng(42), 1), 'fixture')
            args, kwargs = builder.call_args
            self.assertIs(kwargs['augment'], False)
            np.testing.assert_array_equal(kwargs['timing_reference'], pcm)
            self.assertEqual(args[0].shape, pcm.shape)
            middle = args[0][1600:-1600]
            frequencies = np.fft.rfftfreq(len(middle), 1/16000)
            peak = frequencies[np.argmax(abs(np.fft.rfft(middle*np.hanning(len(middle)))))]
            self.assertLess(abs(peak-440), 3)
        np.testing.assert_array_equal(pcm, original)

    def test_preserves_original_metadata_and_types_ordinary_feature_digests(self):
        x = np.zeros((3, 6, 40), np.float32)
        y = np.zeros((3, 2), np.float32); y[0, 1] = 1
        w = np.ones_like(y)
        original = {'sha256': 'original-audio', 'label': 1}
        events = {'proof': {}, 'records': [original]}
        meta, result = complete_base_metadata(x, y, w, [original], events,
                                              ['legacy-positive', 'ChildMandarin', 'public-speech-playlist'])
        self.assertIs(meta[0], original)
        self.assertEqual(len(events['records']), 1)
        self.assertEqual(len(result['records']), 3)
        self.assertEqual(meta[1]['sha256_domain'], 'prepared-TRAIN-feature-example')
        self.assertEqual(meta[2]['contrast_class'], 0)
        self.assertEqual(meta[1]['valid_steps'], 2)
        self.assertFalse(x.any())

    def test_unmapped_positive_or_unknown_source_cannot_be_filled_as_an_ordinary_negative(self):
        x = np.zeros((1, 6, 40), np.float32); y = np.ones((1, 2)); w = np.ones_like(y)
        with self.assertRaises(ValueError): complete_base_metadata(x, y, w, [], {'records': []}, ['ChildMandarin'])
        with self.assertRaises(ValueError): complete_base_metadata(x, y*0, w, [], {'records': []}, ['unknown'])


if __name__ == '__main__': unittest.main()
