import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np

UPSTREAM = os.environ.get('PIKOO_WAKE_UPSTREAM')
if UPSTREAM:
    sys.path.insert(0, UPSTREAM)


@unittest.skipUnless(UPSTREAM and importlib.util.find_spec('tensorflow'), 'Optional pinned training runtime')
class SequenceExportCheckTest(unittest.TestCase):
    def test_trained_sequence_matches_saved_fresh_states_and_corruption_is_detected(self):
        import tensorflow as tf
        from test_causal_model import CausalModelTest
        from causal_model import sequence_view, scalar_view, streaming
        from sequence_export_check import check
        source = CausalModelTest().source(True)
        sequence, _ = sequence_view(source, 180)
        x = np.random.default_rng(55).normal(size=(4,180,40)).astype('float32')
        sequence.compile(optimizer=tf.keras.optimizers.Adam(.001), loss='sparse_categorical_crossentropy')
        sequence.train_on_batch(x, np.zeros((4,60),np.int32))
        wake = scalar_view(sequence)
        with tempfile.TemporaryDirectory() as folder:
            good, bad = Path(folder)/'good', Path(folder)/'bad'
            model = streaming(wake)
            archive = tf.keras.export.ExportArchive();archive.track(model)
            archive.add_endpoint(name='serve',fn=model.call,input_signature=[tf.TensorSpec(model.input.shape,tf.float32)])
            archive.write_out(str(good),verbose=False)
            report = check(wake,good,x,[False,False,True,True],4)
            self.assertEqual(report['status'],'passed-trained-sequence-export-parity')
            self.assertEqual(len(report['cases']),4)
            self.assertEqual(sum(c['steps'] for c in report['cases']),240)
            corrupt = streaming(wake)
            archive = tf.keras.export.ExportArchive();archive.track(corrupt)
            archive.add_endpoint(name='serve',fn=lambda v: corrupt(v)+.1,
                input_signature=[tf.TensorSpec(corrupt.input.shape,tf.float32)])
            archive.write_out(str(bad),verbose=False)
            report = check(wake,bad,x,[False,False,True,True],4)
            self.assertEqual(report['status'],'failed-trained-sequence-export-parity')
            self.assertTrue(all(c['max_absolute_error'] > .09 for c in report['cases']))


if __name__ == '__main__':
    unittest.main()
