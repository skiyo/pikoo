import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec('numpy'), 'Optional training runtime is not installed')
class AcousticAugmentTest(unittest.TestCase):
    def test_band_limit_preserves_speech_band_and_attenuates_edges(self):
        import numpy as np
        from acoustic_augment import bandlimit
        t = np.arange(16000) / 16000
        def energy(frequency):
            signal = np.sin(2 * np.pi * frequency * t)
            return float(np.mean(bandlimit(signal, 200, 3000)[1000:-1000] ** 2))
        middle = energy(1000)
        self.assertGreater(middle, .4)
        self.assertLess(energy(50), middle * .01)
        self.assertLess(energy(7000), middle * .01)

    def test_augmentation_is_deterministic_and_preserves_sample_count(self):
        import numpy as np
        from acoustic_augment import augment
        pcm = np.sin(np.arange(16000) * .15) * 5000
        original = pcm.copy()
        a = augment(pcm, np.random.default_rng(123))
        b = augment(pcm, np.random.default_rng(123))
        np.testing.assert_array_equal(a, b)
        np.testing.assert_array_equal(pcm, original)
        self.assertEqual(a.shape, pcm.shape)
        self.assertTrue(np.all(np.isfinite(a)))


if __name__ == '__main__':
    unittest.main()
