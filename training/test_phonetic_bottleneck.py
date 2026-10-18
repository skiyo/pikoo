import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

TF=importlib.util.find_spec('tensorflow') is not None


@unittest.skipUnless(TF,'Optional TensorFlow runtime is not installed')
class BottleneckTest(unittest.TestCase):
    def test_mismatched_encoder_or_phone_head_is_rejected_before_graph(self):
        from phonetic_bottleneck import attach
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);encoder=root/'encoder.h5';encoder.write_bytes(b'encoder')
            head=root/'phone-head.npz';head.write_bytes(b'not loaded on mismatch')
            meta={'phone_head_sha256':hashlib.sha256(head.read_bytes()).hexdigest(),'encoder_init_sha256':'wrong'}
            head.with_suffix('.json').write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError,'does not match'):attach(None,head,encoder)
            meta['phone_head_sha256']='wrong';head.with_suffix('.json').write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError,'checksum mismatch'):attach(None,head,encoder)

    def test_export_anchor_preserves_float_function_and_all_weights(self):
        import numpy as np
        import tensorflow as tf
        from phonetic_bottleneck import anchor_for_quantization
        tf.keras.utils.set_random_seed(9)
        inp=tf.keras.Input((3,1,4));x=tf.keras.layers.Dense(5)(inp)
        x=tf.keras.layers.Softmax(name='frozen_phone_probabilities')(x)
        x=tf.keras.layers.Flatten()(x);out=tf.keras.layers.Dense(1,activation='sigmoid')(x)
        base=tf.keras.Model(inp,out);anchored=anchor_for_quantization(base)
        fixture=np.random.default_rng(3).normal(size=(5,3,1,4)).astype('float32')
        np.testing.assert_allclose(base(fixture),anchored(fixture),atol=1e-7,rtol=0)
        for layer in base.layers:
            if not layer.get_weights():continue
            for old,new in zip(layer.get_weights(),anchored.get_layer(layer.name).get_weights()):np.testing.assert_array_equal(old,new)
        self.assertFalse(anchored.get_layer('phone_export_scale_anchor').trainable)


if __name__=='__main__':unittest.main()
