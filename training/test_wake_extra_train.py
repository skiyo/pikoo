# SPDX-License-Identifier: Apache-2.0
import unittest
import numpy as np
from wake_extra_train import complete_base_metadata


class ExtraTrainMetadata(unittest.TestCase):
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
