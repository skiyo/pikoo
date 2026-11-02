# SPDX-License-Identifier: Apache-2.0
import copy
import unittest
import numpy as np
from wake_phrase_boundaries import emphasize


class PhraseBoundaries(unittest.TestCase):
    def inputs(self):
        labels = np.zeros((3, 10), np.float32); labels[0, 6:9] = 1
        weights = np.ones_like(labels); weights[:, 9] = 0; weights[0, 5] = 0
        archive = {'proof': {'every_original_TRAIN_array_byte_equal': True,
            'household_used': False, 'DEV_waveforms_read': False, 'TEST_opened': False,
            'source_manifest_labels_unchanged': True},
            'records': [{'label': int(i == 0), 'contrast_class': c, 'valid_steps': 9,
                         'times_ms': [100*j for j in range(1, 10)], 'completion_ms': 700}
                        for i, c in enumerate((1, 2))]}
        return archive, labels, weights

    def test_only_known_negative_boundaries_change_and_padding_stays_masked(self):
        archive, y, w = self.inputs(); original = w.copy()
        result, proof = emphasize(archive, y, w)
        np.testing.assert_array_equal(w, original)
        np.testing.assert_array_equal(result[0, 6:], w[0, 6:])
        np.testing.assert_array_equal(result[2], w[2])
        self.assertEqual(result[0, 5], 0)
        self.assertEqual(result[0, 0], 4)
        self.assertEqual(result[1, 5], 4)
        self.assertEqual(result[1, 0], 1)
        self.assertEqual(proof['factor'], 4)

    def test_protected_metadata_or_positive_overlap_fails_closed(self):
        archive, y, w = self.inputs()
        for key in ('household_used', 'DEV_waveforms_read', 'TEST_opened'):
            bad = copy.deepcopy(archive); bad['proof'][key] = True
            with self.assertRaises(ValueError): emphasize(bad, y, w)
        bad = copy.deepcopy(archive); bad['records'][0]['completion_ms'] = 1000
        with self.assertRaises(ValueError): emphasize(bad, y, w)


if __name__ == '__main__': unittest.main()
