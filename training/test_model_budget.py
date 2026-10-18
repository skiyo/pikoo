import importlib.util
from pathlib import Path
import tempfile
import unittest


@unittest.skipUnless(importlib.util.find_spec('tensorflow'),'Optional training runtime')
class ModelBudgetTest(unittest.TestCase):
    def test_explicit_larger_budget_keeps_quantized_contract_checks(self):
        import numpy as np
        import tensorflow as tf
        from check_esp32_model import check

        @tf.function(input_signature=[tf.TensorSpec([1,3,40],tf.float32)])
        def fixture(x):
            return tf.math.sigmoid(tf.reduce_mean(x,axis=[1,2],keepdims=True))

        converter=tf.lite.TFLiteConverter.from_concrete_functions([fixture.get_concrete_function()],fixture)
        converter.optimizations=[tf.lite.Optimize.DEFAULT]
        converter.representative_dataset=lambda:iter([[np.full((1,3,40),v,np.float32)] for v in [-1,0,1]])
        converter.target_spec.supported_ops=[tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
        converter.inference_input_type=tf.int8
        converter.inference_output_type=tf.uint8
        binary=converter.convert()
        firmware=Path(__file__).parents[1]/'firmware/main/wake_model.cpp'
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'fixture.tflite'
            path.write_bytes(binary+bytes(100000-len(binary)))
            with self.assertRaisesRegex(ValueError,'flash budget'):
                check(path,firmware)
            result=check(path,firmware,131072)
            self.assertEqual(result['flash_budget_bytes'],131072)
            self.assertEqual(result['input_shape'],[1,3,40])
            with self.assertRaisesRegex(ValueError,'registered operator'):
                empty=Path(tmp)/'empty.cpp';empty.write_text('')
                check(path,empty,131072)
            for budget in [65535,524289,-1,float('nan')]:
                with self.assertRaisesRegex(ValueError,'64..512'):
                    check(path,firmware,budget)


if __name__=='__main__':unittest.main()
