# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import tempfile
import unittest

try:
    import numpy as np
    from wake_dual_context import add_short_context
    from wake_int8_iterate import load_profiles
except ImportError:
    add_short_context = None


@unittest.skipIf(add_short_context is None, 'Optional pinned training runtime required')
class DualContext(unittest.TestCase):
    def test_profile_is_bounded_and_opt_in(self):
        base = {'name': 'dual', 'channels': 96, 'head': 64, 'context_steps': 72,
                'initialization': 'checkpoint', 'learning_rate': .0001,
                'max_epochs': 12, 'seeds': [42, 43]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'profile.json'
            path.write_text(json.dumps([base]))
            self.assertNotIn('short_context_steps', load_profiles(path)[0])
            path.write_text(json.dumps([{**base, 'short_context_steps': 20}]))
            self.assertEqual(load_profiles(path)[0]['short_context_steps'], 20)
            for override in ({'short_context_steps': True}, {'short_context_steps': 20.},
                             {'short_context_steps': None}, {'short_context_steps': 72},
                             {'context_steps': 20}, {'initialization': 'fresh'},
                             {'initialization': 'phone-encoder'}, {'batch_normalization': True},
                             {'freeze_checkpoint_encoder': True}):
                path.write_text(json.dumps([{**base, 'short_context_steps': 20, **override}]))
                with self.assertRaises(ValueError): load_profiles(path)

    def test_helper_rejects_unplanned_window_before_model_access(self):
        for steps in (True, None, 20., 10, 72):
            with self.assertRaises(ValueError): add_short_context(object(), steps)

    @unittest.skipUnless(os.environ.get('PIKOO_MWW_UPSTREAM'), 'Existing pinned upstream required')
    def test_donor_function_preserved_and_new_branch_learns(self):
        import tensorflow as tf
        from hi_pikoo_model import build, sequence_loss
        from wake_phrase_auxiliary import attach
        tf.keras.backend.clear_session()
        base = build(Path(os.environ['PIKOO_MWW_UPSTREAM']), 72, 42, 24, head_units=32)
        # Non-default classifier weights ensure this tests transfer, not just
        # a random zero-like initialized output or a silently fresh classifier.
        head = base.get_layer('wake_probability')
        head.set_weights([np.full_like(head.kernel.numpy(), .1), np.asarray([-.5], np.float32)])
        before = [w.numpy().copy() for w in base.weights]
        x = np.random.default_rng(44).uniform(0, 26, (2, 600, 40)).astype(np.float32)
        expected = base(x, training=False).numpy()
        model, proof = add_short_context(base)
        np.testing.assert_allclose(model(x, training=False).numpy(), expected, rtol=1e-5, atol=1e-6)
        for old, w in zip(before, base.weights): np.testing.assert_array_equal(old, w.numpy())
        self.assertEqual((model.input_shape, model.output_shape), (base.input_shape, base.output_shape))
        self.assertGreater(proof['parameters_after'], proof['parameters_before'])
        self.assertIs(model.get_layer('mix_2'), base.get_layer('mix_2'))
        classifier = model.get_layer('wake_probability')
        np.testing.assert_array_equal(classifier.kernel.numpy()[:, :, 32:], 0)
        short_before = [w.numpy().copy() for w in model.get_layer('short_hidden').weights]
        training = attach(model)
        training.compile(optimizer=tf.keras.optimizers.SGD(.01),
            loss={'wake': sequence_loss, 'phrase': tf.keras.losses.SparseCategoricalCrossentropy()},
            loss_weights={'wake': 1., 'phrase': .2})
        labels = {'wake': np.zeros((2, 200), np.float32), 'phrase': np.zeros((2, 200), np.int32)}
        for _ in range(2): training.train_on_batch(x, labels)
        self.assertTrue(np.any(classifier.kernel.numpy()[:, :, 32:] != 0))
        self.assertTrue(any(not np.array_equal(old, w.numpy()) for old, w in
                            zip(short_before, model.get_layer('short_hidden').weights)))
        with self.assertRaises(ValueError): add_short_context(model)
        short_base = build(Path(os.environ['PIKOO_MWW_UPSTREAM']), 20, 42, 24, head_units=32)
        with self.assertRaises(ValueError): add_short_context(short_base)


if __name__ == '__main__': unittest.main()
