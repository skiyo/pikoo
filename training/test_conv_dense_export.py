import importlib.util,tempfile,unittest
from pathlib import Path


@unittest.skipUnless(importlib.util.find_spec('tensorflow'),'Optional pinned TensorFlow unavailable')
class ConvDenseExportTest(unittest.TestCase):
    def test_nonzero_hidden_and_softmax_weights_preserve_all_probabilities(self):
        import numpy as np
        import tensorflow as tf
        from conv_dense_export import replace_dense
        tf.keras.utils.set_random_seed(71)
        x=tf.keras.Input((9,));z=tf.keras.layers.Dense(7,activation='relu',use_bias=False)(x)
        z=tf.keras.layers.Dropout(.2)(z);z=tf.keras.layers.Dense(14,activation='softmax')(z)
        model=tf.keras.Model(x,z);fixture=np.random.default_rng(71).normal(size=(6,9)).astype('float32')
        expected=model(fixture,training=False).numpy();weights=[w.copy() for w in model.get_weights()]
        converted,report=replace_dense(model)
        np.testing.assert_allclose(converted(fixture,training=False),expected,atol=2e-7,rtol=2e-6)
        for before,after in zip(weights,model.get_weights()):np.testing.assert_array_equal(before,after)
        self.assertEqual(len(report['layers']),2)
        self.assertFalse(any(isinstance(l,tf.keras.layers.Dense) for l in converted.layers))

    def test_integer_export_retains_per_channel_convs_and_reference_portability(self):
        import numpy as np
        import tensorflow as tf
        from conv_dense_export import replace_dense
        from streaming_runtime import interpreter,quantize
        from tensorflow.lite.python import schema_py_generated as schema
        tf.keras.utils.set_random_seed(72)
        inp=tf.keras.Input(batch_shape=(1,3,40));x=tf.keras.layers.Flatten()(inp)
        x=tf.keras.layers.Dense(4,activation='relu')(x);out=tf.keras.layers.Dense(1,activation='sigmoid')(x)
        model=tf.keras.Model(inp,out);converted,_=replace_dense(model)
        examples=np.random.default_rng(72).uniform(0,4,(16,1,3,40)).astype('float32')
        converter=tf.lite.TFLiteConverter.from_keras_model(converted)
        converter.optimizations=[tf.lite.Optimize.DEFAULT]
        converter.target_spec.supported_ops=[tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
        converter.inference_input_type=tf.int8;converter.inference_output_type=tf.uint8
        converter._experimental_disable_per_channel_quantization_for_dense_layers=True
        converter.representative_dataset=lambda:([value] for value in examples)
        binary=converter.convert();flat=schema.Model.GetRootAsModel(binary,0);graph=flat.Subgraphs(0);per_channel=0
        for i in range(graph.OperatorsLength()):
            op=graph.Operators(i);code=flat.OperatorCodes(op.OpcodeIndex()).BuiltinCode()
            self.assertNotEqual(code,schema.BuiltinOperator.FULLY_CONNECTED)
            if code==schema.BuiltinOperator.CONV_2D:
                per_channel+=graph.Tensors(op.Inputs(1)).Quantization().ScaleLength()>1
        self.assertGreaterEqual(per_channel,1)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fixture.tflite';path.write_bytes(binary)
            engines=[interpreter(path),tf.lite.Interpreter(model_path=str(path),num_threads=1)]
            for engine in engines:engine.allocate_tensors()
            info=engines[0].get_input_details()[0]
            for value in examples:
                answers=[]
                for engine in engines:
                    engine.set_tensor(engine.get_input_details()[0]['index'],quantize(value,*info['quantization']));engine.invoke()
                    answers.append(int(engine.get_tensor(engine.get_output_details()[0]['index']).flat[0]))
                self.assertLessEqual(abs(answers[0]-answers[1]),2)


if __name__=='__main__':unittest.main()
