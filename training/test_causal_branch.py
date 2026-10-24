import importlib.util
import os
import sys
import unittest
import numpy as np

UPSTREAM = os.environ.get('PIKOO_WAKE_UPSTREAM')
if UPSTREAM:
    sys.path.insert(0, UPSTREAM)


@unittest.skipUnless(UPSTREAM and importlib.util.find_spec('tensorflow'), 'Optional pinned training runtime')
class CausalBranchTest(unittest.TestCase):
    def test_zero_correction_preserves_source_and_nonzero_branch_streams_all_steps(self):
        self.check_branch(0)

    def test_independent_raw_projection_preserves_original_and_streams(self):
        self.check_branch(96)

    def test_expanded_ordered_context_preserves_source_and_streams_after_warmup(self):
        self.check_branch(96, 72)

    def check_branch(self, raw_filters, ordered_steps=20):
        from test_causal_model import CausalModelTest
        from causal_branch import attach, integer_anchor
        from causal_model import replay, streaming, scalar_view
        import tensorflow as tf
        source = CausalModelTest().source()
        frames=360 if ordered_steps==72 else 180
        branch, graph = attach(source, frames, raw_filters=raw_filters, ordered_steps=ordered_steps)
        x = np.random.default_rng(200).normal(size=(frames, 40)).astype('float32')
        expected = replay(streaming(source), x)
        np.testing.assert_allclose(branch(x[None], training=False).numpy()[0], expected, atol=1e-6)
        correction = branch.get_layer('short_context_correction')
        rng = np.random.default_rng(201)
        correction.set_weights([rng.normal(0, .1, v.shape).astype('float32') for v in correction.get_weights()])
        expected = branch(x[None], training=False).numpy()[0]
        np.testing.assert_allclose(replay(streaming(branch), x), expected, atol=1e-6)
        np.testing.assert_allclose(replay(streaming(scalar_view(branch)), x)[:, 0], expected[:, 1], atol=1e-6)
        anchored = integer_anchor(branch)
        np.testing.assert_allclose(anchored(x[None], training=False).numpy()[0], expected, atol=1e-6)
        np.testing.assert_allclose(replay(streaming(anchored), x), expected, atol=1e-6)
        original = {layer.name: layer.get_weights() for layer in branch.layers if not layer.trainable}
        branch.compile(optimizer=tf.keras.optimizers.Adam(.001), loss='sparse_categorical_crossentropy')
        branch.train_on_batch(x[None], np.zeros((1, frames//3), np.int32))
        for name, weights in original.items():
            for before, after in zip(weights, branch.get_layer(name).get_weights()):
                np.testing.assert_array_equal(before, after)
        self.assertEqual(graph['short_context']['ordered_steps'], ordered_steps)
        self.assertEqual(graph['short_context']['raw_first_filters'], raw_filters)
        self.assertGreater(graph['short_context']['trainable_parameters'], 0)


if __name__ == '__main__':
    unittest.main()
