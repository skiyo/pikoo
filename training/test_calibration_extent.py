import unittest
import numpy as np
from calibration_extent import valid_steps


class CalibrationExtentTest(unittest.TestCase):
    def test_interior_uncertainty_is_not_right_padding(self):
        mask = [1, 1, 0, 0, 1, 1, 0, 0]
        self.assertEqual(valid_steps(mask), 6)
        self.assertNotEqual(valid_steps(mask), np.count_nonzero(mask))

    def test_unmasked_recording_keeps_its_original_extent(self):
        self.assertEqual(valid_steps([2, 2, 2, 0, 0]), 3)
        self.assertEqual(valid_steps([1, 1]), 2)

    def test_invalid_or_empty_recordings_cannot_calibrate(self):
        for mask in ([], [0, 0], [1, -1], [1, np.nan], [[1, 0]]):
            with self.subTest(mask=mask), self.assertRaises(ValueError):
                valid_steps(mask)


if __name__ == '__main__':
    unittest.main()
