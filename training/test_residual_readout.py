import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec('tensorflow'),'Optional training runtime')
class ResidualReadoutTest(unittest.TestCase):
    def test_freeze_normalization_keeps_statistics_but_allows_encoder_learning(self):
        import numpy as np
        import tensorflow as tf
        from residual_readout import freeze_normalization
        tf.keras.utils.set_random_seed(11)
        inputs=tf.keras.Input((8,));encoder=tf.keras.layers.Dense(12,activation='relu')
        norm=tf.keras.layers.BatchNormalization();x=norm(encoder(inputs))
        model=tf.keras.Model(inputs,tf.keras.layers.Dense(1,activation='sigmoid')(x))
        samples=np.random.default_rng(11).normal(size=(32,8)).astype('float32')
        freeze_normalization(model)
        frozen=[w.copy() for w in norm.get_weights()];weights=encoder.get_weights()[0].copy()
        model.compile(optimizer=tf.keras.optimizers.Adam(.001),loss='binary_crossentropy')
        model.train_on_batch(samples,np.zeros((32,1),np.float32))
        for a,b in zip(frozen,norm.get_weights()):np.testing.assert_array_equal(a,b)
        self.assertFalse(np.array_equal(weights,encoder.get_weights()[0]))

    def test_initial_function_preserved_and_training_cannot_change_encoder(self):
        import numpy as np
        import tensorflow as tf
        from residual_readout import attach
        tf.keras.utils.set_random_seed(19)
        i=tf.keras.Input((8,));x=tf.keras.layers.Dense(12,activation='relu')(i)
        x=tf.keras.layers.BatchNormalization()(x)
        base=tf.keras.Model(i,tf.keras.layers.Dense(1,activation='sigmoid')(x))
        samples=np.random.default_rng(18).normal(size=(32,8)).astype('float32')
        expected=base(samples,training=False).numpy();before=[w.copy() for w in base.get_weights()]
        model=attach(base,16)
        np.testing.assert_allclose(model(samples,training=False),expected,atol=1e-6,rtol=1e-6)
        self.assertGreater(model.count_params(),base.count_params())
        model.compile(optimizer=tf.keras.optimizers.Adam(.001),loss='binary_crossentropy')
        correction=model.get_layer('wake_logit_correction');old=correction.get_weights()[0].copy()
        for _ in range(3):model.train_on_batch(samples,np.zeros((32,1),np.float32))
        for a,b in zip(before,base.get_weights()):np.testing.assert_array_equal(a,b)
        self.assertFalse(np.array_equal(old,correction.get_weights()[0]))
        self.assertFalse(model.get_layer('wake_frozen_logit').trainable)
        for value in [0,8,257]:
            with self.assertRaisesRegex(ValueError,'16..256'):attach(base,value)


if __name__=='__main__':unittest.main()
