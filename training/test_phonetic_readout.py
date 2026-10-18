import importlib.util
import os
import sys
import unittest
from pathlib import Path


@unittest.skipUnless(importlib.util.find_spec('tensorflow') and os.environ.get('PIKOO_WAKE_UPSTREAM'),
    'Requires optional training runtime and pinned upstream checkout')
class PhoneticReadoutTest(unittest.TestCase):
    def test_preserves_backbone_and_matches_causal_stream(self):
        import numpy as np
        import tensorflow as tf
        from types import SimpleNamespace
        sys.path.insert(0,str(Path(os.environ['PIKOO_WAKE_UPSTREAM']).resolve()))
        from microwakeword import mixednet,utils
        from microwakeword.layers import modes
        from phonetic_readout import attach,anchor_for_quantization
        tf.keras.utils.set_random_seed(14)
        flags=SimpleNamespace(pointwise_filters='16,16,16,16,16,16',repeat_in_block='1,1,1,1,1,1',
            mixconv_kernel_sizes='[5],[9],[13],[21],[31],[43]',residual_connection='0,0,0,0,0,0',
            first_conv_filters=12,first_conv_kernel_size=3,stride=3,spatial_attention=0,pooled=1,max_pool=0)
        base=mixednet.model(flags,(399,40),None)
        samples=np.random.default_rng(14).normal(size=(4,399,40)).astype('float32')
        expected=base(samples,training=False).numpy();before=[w.copy() for w in base.get_weights()]
        model=attach(base)
        np.testing.assert_allclose(model(samples,training=False),expected,atol=1e-6)
        model.compile(optimizer=tf.keras.optimizers.Adam(.001),loss='binary_crossentropy')
        for _ in range(3):model.train_on_batch(samples,np.zeros((4,1),np.float32))
        for a,b in zip(before,base.get_weights()):np.testing.assert_array_equal(a,b)
        expected_stream=model(samples[:1],training=False).numpy()
        model=anchor_for_quantization(model)
        np.testing.assert_allclose(model(samples[:1],training=False),expected_stream,atol=1e-6)
        streaming=utils.to_streaming_inference(model,{'stride':3,'spectrogram_length':399},
            modes.Modes.STREAM_INTERNAL_STATE_INFERENCE)
        for i in range(0,399,3):last=streaming(samples[:1,i:i+3],training=False)
        np.testing.assert_allclose(last,expected_stream,atol=2e-5,rtol=2e-5)
        # Shape/float parity does not prove an ESP32-compatible export: a
        # recurrent branch can silently retain float state after conversion.
        import tempfile
        from check_esp32_model import check
        with tempfile.TemporaryDirectory() as directory:
            export=Path(directory)/'saved'
            archive=tf.keras.export.ExportArchive();archive.track(streaming)
            archive.add_endpoint(name='serve',fn=streaming.call,
                input_signature=[tf.TensorSpec(streaming.input.shape,tf.float32)])
            archive.write_out(str(export),verbose=False)
            converter=tf.lite.TFLiteConverter.from_saved_model(str(export))
            converter.optimizations=[tf.lite.Optimize.DEFAULT]
            converter._experimental_variable_quantization=True
            # Exercise the same portable FC contract enforced by the static
            # checker and production exporter, including optional runtimes.
            converter._experimental_disable_per_channel_quantization_for_dense_layers=True
            converter.target_spec.supported_ops=[tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
            converter.inference_input_type=tf.int8;converter.inference_output_type=tf.uint8
            def representative():
                for i in range(0,399,3):yield [samples[:1,i:i+3]]
            converter.representative_dataset=representative
            path=Path(directory)/'wake.tflite';path.write_bytes(converter.convert())
            result=check(path,Path(__file__).parents[1]/'firmware/main/wake_model.cpp',524288)
            self.assertEqual(result['status'],'static-check-passed')


if __name__=='__main__':unittest.main()
