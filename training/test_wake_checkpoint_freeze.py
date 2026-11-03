# SPDX-License-Identifier: Apache-2.0
"""Checkpoint retention controls: real-gradient boundary check when configured."""
import json
import os
from pathlib import Path
import tempfile
import unittest

try:
    import numpy as np
    from wake_int8_iterate import load_profiles, checkpoint_encoder_policy, verify_frozen_checkpoint_weights
except ImportError:
    checkpoint_encoder_policy = None


@unittest.skipIf(checkpoint_encoder_policy is None, 'Optional pinned training runtime required')
class CheckpointFreeze(unittest.TestCase):
    def test_explicit_boolean_only_for_a_checkpoint_donor(self):
        profile = {'name': 'retention', 'channels': 96, 'head': 64, 'context_steps': 72,
                   'initialization': 'checkpoint', 'learning_rate': .0001,
                   'max_epochs': 12, 'seeds': [42, 43], 'freeze_checkpoint_encoder': True}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'profiles.json'
            for value in (True, False):
                path.write_text(json.dumps([{**profile, 'freeze_checkpoint_encoder': value}]))
                self.assertIs(load_profiles(path)[0]['freeze_checkpoint_encoder'], value)
            for override in ({'freeze_checkpoint_encoder': 'yes'}, {'freeze_checkpoint_encoder': 1},
                             {'initialization': 'fresh'}, {'initialization': 'baseline'},
                             {'initialization': 'phone-encoder'}):
                path.write_text(json.dumps([{**profile, **override}]))
                with self.assertRaises(ValueError): load_profiles(path)

    def test_default_policy_does_not_touch_model_or_load_tensorflow(self):
        self.assertEqual(checkpoint_encoder_policy(object()), {})
        for value in ('yes', 1, None):
            with self.assertRaises(ValueError): checkpoint_encoder_policy(object(), value)

    @unittest.skipUnless(os.environ.get('PIKOO_MWW_UPSTREAM'),
                         'Set PIKOO_MWW_UPSTREAM to the existing pinned upstream for gradient check')
    def test_real_gradient_preserves_all_encoder_weights_and_updates_head(self):
        import tensorflow as tf
        from hi_pikoo_model import build, sequence_loss
        from wake_phrase_auxiliary import attach
        upstream = Path(os.environ['PIKOO_MWW_UPSTREAM'])
        if not upstream.is_dir(): self.fail('Configured pinned upstream is unavailable; never download')
        model = build(upstream, 72, 42, 24, False, head_units=32)
        encoder = tf.keras.Model(model.input, model.get_layer('ordered_context').input)
        before = [w.numpy().copy() for w in encoder.weights]
        head = model.get_layer('wake_probability')
        head_before = [w.numpy().copy() for w in head.weights]
        shape = (model.input_shape, model.output_shape)
        proof = checkpoint_encoder_policy(model, True)
        self.assertEqual(proof['encoder_trainable_layers'], 0)
        self.assertGreater(proof['remaining_trainable_weight_count'], 0)
        self.assertTrue(head.trainable)
        self.assertFalse({id(w) for w in encoder.weights} & {id(w) for w in model.trainable_weights})
        training = attach(model)
        training.compile(optimizer=tf.keras.optimizers.SGD(.01),
                         loss={'wake': sequence_loss, 'phrase': tf.keras.losses.SparseCategoricalCrossentropy()},
                         loss_weights={'wake': 1., 'phrase': .2})
        x = np.random.default_rng(42).uniform(0, 26, (2, 600, 40)).astype(np.float32)
        training.train_on_batch(x, {'wake': np.ones((2, 200), np.float32),
                                    'phrase': np.ones((2, 200), np.int32)})
        for old, weight in zip(before, encoder.weights):
            np.testing.assert_array_equal(weight.numpy(), old)
        verify_frozen_checkpoint_weights(encoder.weights, proof['encoder_weights_sha256'])
        self.assertTrue(any(not np.array_equal(old, w.numpy()) for old, w in zip(head_before, head.weights)))
        self.assertEqual((model.input_shape, model.output_shape), shape)
        # The runtime guard must detect an optimizer/ownership regression,
        # even if layer.trainable still reports the requested frozen flags.
        encoder.weights[0].assign_add(tf.ones_like(encoder.weights[0])*.001)
        with self.assertRaisesRegex(ValueError, 'weights changed'):
            verify_frozen_checkpoint_weights(encoder.weights, proof['encoder_weights_sha256'])


if __name__ == '__main__': unittest.main()
