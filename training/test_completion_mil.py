import importlib.util
import unittest
import numpy as np


@unittest.skipUnless(importlib.util.find_spec('tensorflow'), 'Optional TensorFlow runtime')
class CompletionMILTest(unittest.TestCase):
    def test_negative_event_penalty_detects_a_spike_diluted_by_average_frame_loss(self):
        from completion_mil import loss
        def p(wake):
            out=np.full((1,200,14),1e-10,np.float32);out[0,:,1]=wake;out[0,:,0]=1-np.asarray(wake);return out
        labels=np.zeros((1,200),np.int32);weights=np.ones((1,200),np.float32)
        flat=p(np.full(200,.1));wake=np.full(200,1e-6);wake[80:85]=.95;spike=p(wake)
        self.assertLess(float(loss(labels,spike,weights)),float(loss(labels,flat,weights)))
        self.assertGreater(float(loss(labels,spike,weights,True)),float(loss(labels,flat,weights,True)))

    def test_negative_event_ignores_padding_and_never_penalizes_positive_event(self):
        from completion_mil import loss
        labels,weights=self.inputs();wake=np.full(16,.02);wake[5:10]=.99
        p=self.probabilities(wake)
        self.assertAlmostEqual(float(loss(labels,p,weights)),float(loss(labels,p,weights,True)),places=5)
        labels[:]=0;weights[:]=1;weights[:,14:]=0;wake[:]=.02
        expected=float(loss(labels,self.probabilities(wake),weights,True));wake[14:]=.99999
        self.assertAlmostEqual(float(loss(labels,self.probabilities(wake),weights,True)),expected,places=5)

    def test_saturated_negative_still_has_finite_nonzero_reject_gradient(self):
        import tensorflow as tf
        from completion_mil import loss
        values=np.zeros((1,16,14),np.float32);values[:,:,1]=30
        logits=tf.Variable(values)
        with tf.GradientTape() as tape:
            value=loss(np.zeros((1,16),np.int32),tf.nn.softmax(logits),np.ones((1,16),np.float32),True)
        gradient=tape.gradient(value,logits).numpy()
        self.assertTrue(np.isfinite(gradient).all());self.assertGreater(float(gradient[:,:,1].sum()),.5)

    def inputs(self):
        labels = np.zeros((1, 16), np.int32)
        labels[:, 10:14] = 1
        weights = np.ones((1, 16), np.float32)
        weights[:, 5:10] = 0
        weights[:, 10:14] = 6
        weights[:, 14:] = 0
        return labels, weights

    def probabilities(self, wake):
        wake = np.asarray(wake, np.float32).reshape(-1, 16)
        p = np.full((*wake.shape, 14), 1e-10, np.float32)
        p[..., 0], p[..., 1] = 1-wake, wake
        return p

    def test_complete_eligible_window_may_precede_file_end_and_later_decay(self):
        from completion_mil import loss
        labels, weights = self.inputs()
        wake = np.full(16, .01);wake[5:10] = .99
        actual = float(loss(labels, self.probabilities(wake), weights))
        expected = (5/16+24/16)*-np.log(.99)
        self.assertAlmostEqual(actual, expected, places=5)
        wake[5:9] = .01
        self.assertGreater(float(loss(labels, self.probabilities(wake), weights)), actual+1)

    def test_padding_and_early_prefix_cannot_satisfy_positive_event(self):
        from completion_mil import loss
        labels, weights = self.inputs()
        wake = np.full(16, .02)
        original = float(loss(labels, self.probabilities(wake), weights))
        wake[14:] = .999
        self.assertAlmostEqual(float(loss(labels, self.probabilities(wake), weights)), original, places=5)
        wake[:5] = .999
        self.assertGreater(float(loss(labels, self.probabilities(wake), weights)), original)

    def test_every_negative_step_keeps_unchanged_weighted_class_loss(self):
        import tensorflow as tf
        from completion_mil import loss
        labels = np.zeros((2,16),np.int32);labels[1,12:] = 3
        logits = np.random.default_rng(4).normal(size=(2,16,14)).astype('float32')
        p = tf.nn.softmax(logits)
        weights = np.random.default_rng(5).uniform(.5,4,(2,16)).astype('float32')
        expected = tf.reduce_mean(tf.keras.losses.sparse_categorical_crossentropy(labels,p)*weights)
        self.assertAlmostEqual(float(loss(labels,p,weights)),float(expected),places=5)

    def test_constant_positive_predictions_match_previous_loss_mass(self):
        import tensorflow as tf
        from completion_mil import loss
        labels, weights = self.inputs();p = self.probabilities(np.full(16,.8))
        expected = tf.reduce_mean(tf.keras.losses.sparse_categorical_crossentropy(labels,p)*weights)
        self.assertAlmostEqual(float(loss(labels,p,weights)),float(expected),places=5)

    def test_missing_five_step_region_fails_and_gradients_are_finite(self):
        import tensorflow as tf
        from completion_mil import loss
        labels, weights = self.inputs()
        broken = np.ones_like(weights);broken[:,14:] = 0
        with self.assertRaises(tf.errors.InvalidArgumentError):
            loss(labels,self.probabilities(np.full(16,.5)),broken)
        logits = tf.Variable(np.random.default_rng(6).normal(size=(1,16,14)).astype('float32'))
        with tf.GradientTape() as tape:value = loss(labels,tf.nn.softmax(logits),weights)
        gradient = tape.gradient(value,logits).numpy()
        self.assertTrue(np.isfinite(gradient).all());self.assertGreater(np.max(abs(gradient)),0)

    def test_trainer_updates_existing_head_and_preserves_frozen_encoder(self):
        import tensorflow as tf
        from completion_mil import trainer
        tf.keras.utils.set_random_seed(88)
        inp = tf.keras.Input((16,3));encoded = tf.keras.layers.Dense(4,trainable=False)(inp)
        network = tf.keras.Model(inp,tf.keras.layers.Dense(14,activation='softmax')(encoded))
        frozen = network.layers[1].get_weights();head = network.layers[-1].get_weights()
        labels, weights = self.inputs()
        labels=np.concatenate([labels,np.zeros_like(labels)]);weights=np.concatenate([weights,np.ones_like(weights)])
        x = np.random.default_rng(2).normal(size=(2,16,3)).astype('float32')
        for negative_events in (False,True):
            fit = trainer(network,negative_events=negative_events);fit.compile(optimizer=tf.keras.optimizers.Adam(.01))
            fit.train_on_batch(x,labels,sample_weight=weights)
        for a,b in zip(frozen,network.layers[1].get_weights()):np.testing.assert_array_equal(a,b)
        self.assertTrue(any(not np.array_equal(a,b) for a,b in zip(head,network.layers[-1].get_weights())))
        np.testing.assert_allclose(fit(x,training=False),network(x,training=False),atol=1e-7)


if __name__ == '__main__':
    unittest.main()
