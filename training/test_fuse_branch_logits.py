import importlib.util
import unittest
import numpy as np


@unittest.skipUnless(importlib.util.find_spec('tensorflow'), 'Optional training runtime')
class FuseBranchLogitsTest(unittest.TestCase):
    def model(self, activation=None):
        import tensorflow as tf
        tf.keras.utils.set_random_seed(421)
        x = tf.keras.Input((20, 1, 8))
        hidden = tf.keras.layers.Conv2D(5, 1, activation='relu6')(x)
        left = tf.keras.layers.Conv2D(14, 1, name='short_context_original_logits')(x)
        right = tf.keras.layers.Conv2D(14, 1, activation=activation,
                                       name='short_context_correction')(hidden)
        logits = tf.keras.layers.Add(name='short_context_corrected_logits')([left, right])
        out = tf.keras.layers.Softmax(name='short_context_probability')(logits)
        return tf.keras.Model(x, tf.keras.layers.Reshape((-1, 14))(out))

    def test_same_float_function_without_mutating_or_refitting_source(self):
        from fuse_branch_logits import fuse
        model = self.model()
        before = [w.copy() for w in model.get_weights()]
        x = np.random.default_rng(42).normal(size=(3, 20, 1, 8)).astype('float32')
        fused = fuse(model)
        np.testing.assert_allclose(fused(x, training=False).numpy(),
                                   model(x, training=False).numpy(), atol=1e-6)
        for left, right in zip(before, model.get_weights()):
            np.testing.assert_array_equal(left, right)
        self.assertFalse(any(layer.name == 'short_context_corrected_logits' for layer in fused.layers))
        self.assertEqual(fused.get_layer('short_context_fused_logits').kernel.shape[-2:], (13, 14))

    def test_cancelling_bias_is_combined_before_integer_export(self):
        from fuse_branch_logits import fuse
        model = self.model()
        for name, sign in [('short_context_original_logits', 1), ('short_context_correction', -1)]:
            layer = model.get_layer(name)
            kernel, bias = layer.get_weights()
            layer.set_weights([kernel, np.full_like(bias, sign * 100)])
        fused = fuse(model)
        np.testing.assert_array_equal(fused.get_layer('short_context_fused_logits').get_weights()[1], 0)

    def test_nonlinear_head_is_never_silently_fused(self):
        from fuse_branch_logits import fuse
        with self.assertRaisesRegex(ValueError, 'linear'):
            fuse(self.model('relu'))

    def test_optional_centering_keeps_probabilities_and_adds_no_runtime_reduction(self):
        from fuse_branch_logits import fuse
        model = self.model()
        centered = fuse(model, center=True)
        x = np.random.default_rng(43).normal(size=(2, 20, 1, 8)).astype('float32')
        np.testing.assert_allclose(centered(x, training=False).numpy(),
                                   model(x, training=False).numpy(), atol=1e-6)
        kernel, bias = centered.get_layer('short_context_fused_logits').get_weights()
        np.testing.assert_allclose(kernel.mean(axis=-1), 0, atol=1e-7)
        self.assertAlmostEqual(float(bias.mean()), 0, places=6)
        self.assertFalse(any('reduction' in layer.name for layer in centered.layers))
        with self.assertRaises(ValueError):
            fuse(model, center='yes')


if __name__ == '__main__':
    unittest.main()
