import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec('tensorflow'),'Optional TensorFlow runtime not installed')
class SequenceReadoutTest(unittest.TestCase):
    def baseline(self,zero=True):
        import tensorflow as tf
        inp=tf.keras.Input((30,1,4));x=tf.keras.layers.Conv2D(8,1,activation='relu',name='source_encoder')(inp)
        x=tf.keras.layers.AveragePooling2D((30,1))(x);x=tf.keras.layers.Flatten()(x)
        out=tf.keras.layers.Dense(1,activation='sigmoid',kernel_initializer='zeros' if zero else 'ones',bias_initializer='zeros')(x)
        return tf.keras.Model(inp,out)
    def test_zero_initialization_and_acoustic_weights_remain_frozen(self):
        import numpy as np
        import tensorflow as tf
        from sequence_readout import attach
        tf.keras.utils.set_random_seed(21);base=self.baseline();model=attach(base)
        fixture=np.random.default_rng(21).normal(size=(8,30,1,4)).astype('float32')
        np.testing.assert_array_equal(model(fixture).numpy(),base(fixture).numpy())
        original=[w.copy() for w in base.get_layer('source_encoder').get_weights()]
        model.compile(optimizer=tf.keras.optimizers.SGD(.01),loss='binary_crossentropy')
        model.train_on_batch(fixture,np.array([0,1]*4,dtype='float32'))
        for before,after in zip(original,model.get_layer('source_encoder').get_weights()):np.testing.assert_array_equal(before,after)
        self.assertTrue(any(np.any(w!=0) for w in model.get_layer('sequence_wake_probability').get_weights()))
    def test_preexisting_classifier_cannot_silently_be_replaced(self):
        from sequence_readout import attach
        with self.assertRaisesRegex(ValueError,'zero classifier'):attach(self.baseline(False))
    def test_explicit_joint_training_preserves_normalization_and_anchor(self):
        import numpy as np
        import tensorflow as tf
        from sequence_readout import attach
        tf.keras.utils.set_random_seed(24)
        inp=tf.keras.Input((30,1,4));x=tf.keras.layers.Conv2D(8,1,activation='relu',name='source_encoder')(inp)
        x=tf.keras.layers.BatchNormalization(name='source_normalization')(x)
        x=tf.keras.layers.AveragePooling2D((30,1))(x);x=tf.keras.layers.Flatten()(x)
        out=tf.keras.layers.Dense(1,activation='sigmoid',kernel_initializer='zeros',bias_initializer='zeros')(x)
        base=tf.keras.Model(inp,out);model=attach(base,train_encoder=True)
        encoder=model.get_layer('source_encoder');norm=model.get_layer('source_normalization');anchor=model.get_layer('sequence_integer_anchor')
        self.assertTrue(encoder.trainable);self.assertFalse(norm.trainable);self.assertFalse(anchor.trainable)
        original=[w.copy() for w in encoder.get_weights()];statistics=[w.copy() for w in norm.get_weights()];identity=anchor.get_weights()[0].copy()
        fixture=np.random.default_rng(24).normal(size=(8,30,1,4)).astype('float32')
        model.compile(optimizer=tf.keras.optimizers.SGD(.1),loss='binary_crossentropy')
        for _ in range(3):model.train_on_batch(fixture,np.array([0,1]*4,dtype='float32'))
        self.assertTrue(any(np.any(before!=after) for before,after in zip(original,encoder.get_weights())))
        for before,after in zip(statistics,norm.get_weights()):np.testing.assert_array_equal(before,after)
        np.testing.assert_array_equal(identity,anchor.get_weights()[0])


if __name__=='__main__':unittest.main()
