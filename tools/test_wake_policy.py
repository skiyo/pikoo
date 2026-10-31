# SPDX-License-Identifier: Apache-2.0
import hashlib
import tempfile
import unittest
from pathlib import Path
from check_wake_policy import validate, frontend_fingerprint


class WakePolicyTest(unittest.TestCase):
    def test_model_frontend_and_dev_result_are_bound_to_policy(self):
        with tempfile.TemporaryDirectory() as d:
            model = Path(d)/'model.tflite'
            model.write_bytes(b'private model fixture')
            policy = {'target': 'hi-piku-v1', 'schema_version': 1,
                'model_sha256': hashlib.sha256(model.read_bytes()).hexdigest(),
                'rolling': 3, 'threshold': .9,
                'frontend': {'sample_rate': 16000, 'feature_bins': 40,
                    'window_ms': 30, 'feature_step_ms': 10, 'inference_step_ms': 30},
                'frontend_fingerprint': frontend_fingerprint(),
                'development_passed': True, 'candidate_frozen_at': 'fixture'}
            self.assertEqual(validate(model, policy)['rolling'], 3)
            dual = {**policy, 'target': 'hi-piku-piko-v2', 'accepted_names': ['piku', 'piko']}
            self.assertEqual(validate(model, dual)['accepted_names'], ['piku', 'piko'])
            with self.assertRaises(ValueError):
                validate(model, {**dual, 'accepted_names': ['piku']})
            for key, value in [('model_sha256', 'wrong'), ('rolling', 4),
                               ('development_passed', False), ('frontend_fingerprint', '0'*64)]:
                with self.assertRaises(ValueError):
                    validate(model, {**policy, key: value})
