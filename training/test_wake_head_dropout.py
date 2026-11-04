# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import tempfile
import unittest

try:
    import numpy as np
    from wake_head_dropout import add_head_dropout
    from wake_int8_iterate import load_profiles
except ImportError:
    add_head_dropout = None


@unittest.skipIf(add_head_dropout is None, 'Optional pinned training runtime required')
class HeadDropout(unittest.TestCase):
    def test_only_the_predeclared_isolated_control_is_eligible(self):
        profile = {'name': 'dropout', 'channels': 96, 'head': 64, 'context_steps': 72,
                   'initialization': 'checkpoint', 'learning_rate': .0001,
                   'max_epochs': 12, 'seeds': [42, 43]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'profile.json'
            path.write_text(json.dumps([profile]))
            self.assertNotIn('classifier_dropout', load_profiles(path)[0])
            path.write_text(json.dumps([{**profile, 'classifier_dropout': .2}]))
            self.assertEqual(load_profiles(path)[0]['classifier_dropout'], .2)
            for override in ({'classifier_dropout': None}, {'classifier_dropout': True},
                             {'classifier_dropout': 0}, {'classifier_dropout': .1},
                             {'classifier_dropout': .5}, {'short_context_steps': 20},
                             {'freeze_checkpoint_encoder': True}, {'batch_normalization': True},
                             {'context_steps': 20}, {'initialization': 'fresh'}):
                path.write_text(json.dumps([{**profile, 'classifier_dropout': .2, **override}]))
                with self.assertRaises(ValueError): load_profiles(path)

    def test_helper_rejects_unknown_rate_and_seed_before_graph_access(self):
        for rate, seed in [(None, 42), (True, 42), (.1, 42), (.5, 42), (.2, True), (.2, 44)]:
            with self.assertRaises(ValueError): add_head_dropout(object(), rate, seed)

    @unittest.skipUnless(os.environ.get('PIKOO_MWW_UPSTREAM'), 'Existing pinned upstream required')
    def test_same_inference_utterancewise_training_mask_and_auxiliary_gradient(self):
        import tensorflow as tf
        from hi_pikoo_model import build, sequence_loss
        from wake_phrase_auxiliary import attach
        tf.keras.backend.clear_session()
        base = build(Path(os.environ['PIKOO_MWW_UPSTREAM']), 72, 42, 24, head_units=32)
        old_head = base.get_layer('wake_probability')
        old_head.set_weights([np.full_like(old_head.kernel.numpy(), .1), np.asarray([-.5], np.float32)])
        x = np.random.default_rng(45).uniform(0, 26, (2, 600, 40)).astype(np.float32)
        expected = base(x, training=False).numpy()
        model, proof = add_head_dropout(base)
        np.testing.assert_allclose(model(x, training=False).numpy(), expected, rtol=1e-6, atol=1e-6)
        self.assertEqual(model.count_params(), base.count_params())
        self.assertIs(model.get_layer('mix_2'), base.get_layer('mix_2'))
        dropout = model.get_layer('wake_head_dropout')
        values = tf.ones((2, 200, 1, 32))
        mask = dropout(values, training=True).numpy()
        np.testing.assert_array_equal(mask, np.repeat(mask[:, :1], 200, axis=1))
        self.assertTrue(np.any(mask == 0))
        self.assertTrue(np.any(mask == 1.25))
        np.testing.assert_array_equal(dropout(values, training=False).numpy(), values.numpy())
        self.assertIs(model.get_layer('wake_probability').input, dropout.output)
        before = model.get_layer('wake_probability').kernel.numpy().copy()
        training = attach(model)
        training.compile(optimizer=tf.keras.optimizers.SGD(.01),
            loss={'wake': sequence_loss, 'phrase': tf.keras.losses.SparseCategoricalCrossentropy()},
            loss_weights={'wake': 1., 'phrase': .2})
        training.train_on_batch(x, {'wake': np.zeros((2, 200), np.float32),
                                    'phrase': np.zeros((2, 200), np.int32)})
        self.assertTrue(np.any(before != model.get_layer('wake_probability').kernel.numpy()))
        self.assertEqual(proof['parameters_before'], proof['parameters_after'])
        with self.assertRaises(ValueError): add_head_dropout(model)


if __name__ == '__main__': unittest.main()
