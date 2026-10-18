import importlib.util
import os
import sys
import unittest


@unittest.skipUnless(importlib.util.find_spec('tensorflow'),'Optional training runtime')
class RegularizationTest(unittest.TestCase):
    def test_relu6_bounds_values_but_retains_weights_and_original_graph(self):
        import numpy as np
        import tensorflow as tf
        from regularization import with_relu6
        inputs=tf.keras.Input((2,))
        dense=tf.keras.layers.Dense(2,kernel_initializer='identity',bias_initializer='zeros')
        base=tf.keras.Model(inputs,tf.keras.layers.Activation('relu')(dense(inputs)))
        bounded=with_relu6(base);sample=np.array([[-3.,12.]],np.float32)
        np.testing.assert_array_equal(base(sample),[[0.,12.]])
        np.testing.assert_array_equal(bounded(sample),[[0.,6.]])
        for before,after in zip(base.get_weights(),bounded.get_weights()):
            np.testing.assert_array_equal(before,after)

    @unittest.skipUnless(os.environ.get('PIKOO_WAKE_UPSTREAM'),'Requires pinned upstream checkout')
    def test_bounded_sequence_preserves_full_window_streaming_alignment(self):
        import numpy as np
        import tensorflow as tf
        from types import SimpleNamespace
        from regularization import with_relu6
        from sequence_readout import attach
        sys.path.insert(0,os.environ['PIKOO_WAKE_UPSTREAM'])
        from microwakeword import mixednet,utils
        from microwakeword.layers import modes
        flags=SimpleNamespace(pointwise_filters='24,24',repeat_in_block='1,1',
            mixconv_kernel_sizes='[3],[5]',residual_connection='0,0',
            first_conv_filters=16,first_conv_kernel_size=3,stride=3,
            spatial_attention=0,pooled=1,max_pool=0)
        base=mixednet.model(flags,(198,40),None)
        base.layers[-1].set_weights([np.zeros_like(w) for w in base.layers[-1].get_weights()])
        model=attach(with_relu6(base),train_encoder=True,relu6=True)
        head=model.layers[-1];head.set_weights([np.full_like(w,.02) for w in head.get_weights()])
        sample=np.random.default_rng(31).uniform(0,40,(1,198,40)).astype('float32')
        expected=model(sample,training=False).numpy()
        streaming=utils.to_streaming_inference(model,{'stride':3,'spectrogram_length':198},
            modes.Modes.STREAM_INTERNAL_STATE_INFERENCE)
        for i in range(0,198,3):last=streaming(sample[:,i:i+3],training=False)
        np.testing.assert_allclose(last,expected,atol=2e-5,rtol=2e-5)

    @unittest.skipUnless(os.environ.get('PIKOO_WAKE_UPSTREAM'),'Requires pinned upstream checkout')
    def test_regularized_causal_encoder_matches_streaming_inference(self):
        import numpy as np
        import tensorflow as tf
        from types import SimpleNamespace
        from regularization import with_dropout
        sys.path.insert(0,os.environ['PIKOO_WAKE_UPSTREAM'])
        from microwakeword import mixednet,utils
        from microwakeword.layers import modes
        flags=SimpleNamespace(pointwise_filters='24,24,24,24',repeat_in_block='1,1,1,1',
            mixconv_kernel_sizes='[5],[9],[13],[21]',residual_connection='0,0,0,0',
            first_conv_filters=16,first_conv_kernel_size=3,stride=3,spatial_attention=0,pooled=1,max_pool=0)
        model=with_dropout(mixednet.model(flags,(198,40),None),.15)
        samples=np.random.default_rng(16).normal(size=(1,198,40)).astype('float32')
        expected=model(samples,training=False).numpy()
        streaming=utils.to_streaming_inference(model,{'stride':3,'spectrogram_length':198},
            modes.Modes.STREAM_INTERNAL_STATE_INFERENCE)
        for i in range(0,198,3):last=streaming(samples[:,i:i+3],training=False)
        np.testing.assert_allclose(last,expected,atol=2e-5,rtol=2e-5)

    def test_dropout_changes_training_but_preserves_inference_and_parameters(self):
        import numpy as np
        import tensorflow as tf
        from regularization import with_dropout
        tf.keras.utils.set_random_seed(15)
        inputs=tf.keras.Input((8,));x=tf.keras.layers.Dense(24)(inputs)
        x=tf.keras.layers.Activation('relu')(x)
        base=tf.keras.Model(inputs,tf.keras.layers.Dense(1,activation='sigmoid')(x))
        samples=np.ones((16,8),np.float32);model=with_dropout(base,.15)
        self.assertEqual(base.count_params(),model.count_params())
        np.testing.assert_allclose(model(samples,training=False),base(samples,training=False),atol=1e-7)
        self.assertFalse(np.array_equal(model(samples,training=True),model(samples,training=True)))
        for rate in [0,-.1,.5,float('nan')]:
            with self.assertRaisesRegex(ValueError,'Dropout'):with_dropout(base,rate)


if __name__=='__main__':unittest.main()
