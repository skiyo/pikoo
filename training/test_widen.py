import importlib.util
import unittest

@unittest.skipUnless(importlib.util.find_spec('tensorflow'),'Optional training runtime')
class WidenTest(unittest.TestCase):
    def test_original_function_survives_additional_independent_channels(self):
        import tensorflow as tf
        import numpy as np
        from widen import warm_start_wider
        def network(width):
            i=tf.keras.Input((12,5,1));x=tf.keras.layers.Conv2D(width,(3,1),activation='relu')(i)
            x=tf.keras.layers.DepthwiseConv2D((3,1))(x);x=tf.keras.layers.Conv2D(width,(1,1))(x)
            x=tf.keras.layers.BatchNormalization()(x);x=tf.keras.layers.GlobalAveragePooling2D()(x)
            return tf.keras.Model(i,tf.keras.layers.Dense(1,activation='sigmoid')(x))
        tf.keras.utils.set_random_seed(7);small,large=network(4),network(7);warm_start_wider(large,small)
        x=np.random.default_rng(9).normal(size=(5,12,5,1)).astype('float32')
        np.testing.assert_allclose(small(x,training=False),large(x,training=False),rtol=1e-5,atol=1e-6)
        self.assertTrue(np.any(large.layers[1].get_weights()[0][... ,4:]!=0))

if __name__=='__main__':unittest.main()
