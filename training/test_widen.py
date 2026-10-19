import importlib.util
import os
import unittest

@unittest.skipUnless(importlib.util.find_spec('tensorflow'),'Optional training runtime')
class WidenTest(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('PIKOO_WAKE_UPSTREAM'),'Requires pinned upstream checkout')
    def test_actual_wider_mixednet_preserves_trained_classes_and_streaming_alignment(self):
        import tensorflow as tf
        import numpy as np
        import sys,tempfile,json,hashlib
        from pathlib import Path
        from types import SimpleNamespace
        from contrastive_readout import attach,widen_readout,PHRASES
        sys.path.insert(0,os.environ['PIKOO_WAKE_UPSTREAM'])
        from microwakeword import mixednet,utils
        from microwakeword.layers import modes
        def binary(d):
            flags=SimpleNamespace(pointwise_filters=','.join([str(d['filters'])]*2),repeat_in_block='1,1',
                mixconv_kernel_sizes='[3],[5]',residual_connection='0,0',first_conv_filters=d['first_filters'],
                first_conv_kernel_size=3,stride=3,spatial_attention=0,pooled=1,max_pool=0)
            return mixednet.model(flags,(198,40),None)
        small={'filters':8,'first_filters':6,'kernels':[3,5]};large={**small,'filters':12,'first_filters':10,'window_frames':198}
        tf.keras.utils.set_random_seed(117);source,source_view=attach(binary(small),warm_start=True)
        fixture=np.random.default_rng(117).uniform(0,40,(2,198,40)).astype('float32')
        source.compile(optimizer=tf.keras.optimizers.SGD(.01),loss='sparse_categorical_crossentropy')
        source.train_on_batch(fixture,np.array([0,1]))
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'checkpoint.weights.h5';source_view.save_weights(path)
            (root/'report.json').write_text(json.dumps({**small,'feature_config':{'window_frames':198},
                'classifier_readout':{'type':'warm-plain-near-phrase','classes':PHRASES},
                'checkpoint_weights_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}))
            training,view=attach(binary(large),warm_start=True)
            proof=widen_readout(training,view,path,fixture,large,binary)
            self.assertLess(proof['all_class_initial_max_difference'],1e-5)
            expected=view(fixture[:1],training=False).numpy()
            stream=utils.to_streaming_inference(view,{'stride':3,'spectrogram_length':198},modes.Modes.STREAM_INTERNAL_STATE_INFERENCE)
            for start in range(0,198,3):last=stream(fixture[:1,start:start+3],training=False)
            np.testing.assert_allclose(last,expected,atol=2e-5,rtol=2e-5)

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
