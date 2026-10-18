import importlib.util
from pathlib import Path
import tempfile
import unittest


@unittest.skipUnless(importlib.util.find_spec('tensorflow'),'Optional pinned TensorFlow runtime not installed')
class DensePortabilityTest(unittest.TestCase):
    def test_multi_output_dense_requires_portable_scales_and_engines_agree(self):
        import numpy as np
        import tensorflow as tf
        from streaming_runtime import validate_reference_quantization,interpreter
        tf.keras.utils.set_random_seed(17)
        inp=tf.keras.Input(batch_shape=(1,3,40));x=tf.keras.layers.Flatten()(inp)
        x=tf.keras.layers.Dense(4,activation='relu')(x);out=tf.keras.layers.Dense(1,activation='sigmoid')(x)
        model=tf.keras.Model(inp,out)
        fixtures=np.random.default_rng(17).uniform(0,10,(12,1,3,40)).astype('float32')
        def convert(portable):
            converter=tf.lite.TFLiteConverter.from_keras_model(model)
            converter.optimizations=[tf.lite.Optimize.DEFAULT]
            converter.target_spec.supported_ops=[tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
            converter.inference_input_type=tf.int8;converter.inference_output_type=tf.uint8
            converter._experimental_disable_per_channel_quantization_for_dense_layers=portable
            converter.representative_dataset=lambda:([a] for a in fixtures)
            return converter.convert()
        legacy=convert(False)
        with self.assertRaisesRegex(ValueError,'Per-channel FullyConnected'):validate_reference_quantization(legacy)
        portable=convert(True);validate_reference_quantization(portable)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'fixture.tflite';path.write_bytes(portable)
            ref=interpreter(path);fast=tf.lite.Interpreter(model_path=str(path),num_threads=1)
            for runtime in [ref,fast]:runtime.allocate_tensors()
            info=ref.get_input_details()[0];scale,zero=info['quantization']
            for value in fixtures:
                quantized=np.clip(np.rint(value/scale)+zero,-128,127).astype('int8')
                answers=[]
                for runtime in [ref,fast]:
                    runtime.set_tensor(runtime.get_input_details()[0]['index'],quantized);runtime.invoke();answers.append(int(runtime.get_tensor(runtime.get_output_details()[0]['index']).flat[0]))
                self.assertLessEqual(abs(answers[0]-answers[1]),2)


if __name__=='__main__':unittest.main()
