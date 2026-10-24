import importlib.util
import os
import sys
import unittest
from pathlib import Path
import numpy as np

UPSTREAM = os.environ.get('PIKOO_WAKE_UPSTREAM')
if UPSTREAM:
    sys.path.insert(0, UPSTREAM)
AVAILABLE = bool(UPSTREAM) and bool(importlib.util.find_spec('tensorflow'))


@unittest.skipUnless(AVAILABLE, 'Set PIKOO_WAKE_UPSTREAM and use the training runtime')
class CausalModelTest(unittest.TestCase):
    def source(self, residual=False):
        from types import SimpleNamespace
        import tensorflow as tf
        from microwakeword import mixednet
        from contrastive_readout import attach, attach_frozen_residual
        tf.keras.utils.set_random_seed(193)
        flags = SimpleNamespace(pointwise_filters='8,8', repeat_in_block='1,1',
            mixconv_kernel_sizes='[3],[5]', residual_connection='0,0',
            first_conv_filters=4, first_conv_kernel_size=3, stride=3,
            spatial_attention=0, pooled=1, max_pool=0)
        source, _ = attach(mixednet.model(flags, (39, 40), None), warm_start=True)
        # Deliberately nontrivial BN statistics and readout weights expose
        # wrong cold-state padding; zero classifiers would hide alignment bugs.
        rng = np.random.default_rng(21)
        for layer in source.layers:
            if isinstance(layer, tf.keras.layers.BatchNormalization):
                gamma, beta, mean, variance = layer.get_weights()
                layer.set_weights([gamma*.8, beta+.2, mean+.3, variance*.7])
        head = source.get_layer('near_phrase_probability')
        head.set_weights([rng.normal(0, .4, (8, 14)).astype('float32'),
                          rng.normal(0, .2, 14).astype('float32')])
        return attach_frozen_residual(source, 16)[0] if residual else source

    def test_all_steps_and_all_classes_equal_original_cold_stream(self):
        from causal_model import sequence_view, streaming, replay, scalar_view
        for residual in (False, True):
            source = self.source(residual)
            sequence, proof = sequence_view(source, 180)
            features = np.random.default_rng(39).normal(0, 1, (180, 40)).astype('float32')
            expected = replay(streaming(source), features)
            actual = sequence(features[None], training=False).numpy()[0]
            np.testing.assert_allclose(actual, expected, atol=1e-6)
            np.testing.assert_allclose(replay(streaming(sequence), features), expected, atol=1e-6)
            wake = scalar_view(sequence)
            np.testing.assert_allclose(wake(features[None], training=False).numpy()[0], expected[:, 1], atol=1e-6)
            np.testing.assert_allclose(replay(streaming(wake), features)[:, 0], expected[:, 1], atol=1e-6)
            self.assertEqual(tuple(streaming(wake).output.shape), (1, 1))
            self.assertEqual(proof['source_pool_steps'], 7)
            self.assertFalse(proof['inference_horizon_changed'])

    def test_frozen_source_stays_unchanged_after_sequence_training(self):
        import tensorflow as tf
        from causal_model import sequence_view
        source = self.source(True)
        sequence, _ = sequence_view(source, 180)
        before = {layer.name: layer.get_weights() for layer in sequence.layers if not layer.trainable}
        x = np.random.default_rng(13).normal(size=(2, 180, 40)).astype('float32')
        original = sequence(x, training=False).numpy()
        sequence.compile(optimizer=tf.keras.optimizers.Adam(.01), loss='sparse_categorical_crossentropy')
        sequence.train_on_batch(x, np.zeros((2, 60), np.int32))
        self.assertGreater(np.max(abs(sequence(x, training=False).numpy()-original)), 1e-6)
        for name, weights in before.items():
            for expected, actual in zip(weights, sequence.get_layer(name).get_weights()):
                np.testing.assert_array_equal(actual, expected)

    def test_rejects_unsupported_shapes_and_scalar_source(self):
        from causal_model import sequence_view, scalar_view
        source = self.source()
        for frames in (0, 179, 180.0):
            with self.assertRaises(ValueError):
                sequence_view(source, frames)
        sequence, _ = sequence_view(source, 180)
        with self.assertRaises(ValueError):
            sequence_view(scalar_view(sequence), 180)


if __name__ == '__main__':
    unittest.main()
