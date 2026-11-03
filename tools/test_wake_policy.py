# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from check_wake_policy import validate, frontend_fingerprint


class WakePolicyTest(unittest.TestCase):
    def test_generated_header_binds_live_diagnostics_to_both_file_hashes(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);model=root/'model.fixture';model.write_bytes(b'not-a-real-model-fixture')
            policy={'schema_version':1,'target':'hi-piku-piko-v2','accepted_names':['piku','piko'],
                'model_sha256':hashlib.sha256(model.read_bytes()).hexdigest(),'rolling':3,'threshold':.9,
                'frontend':{'sample_rate':16000,'feature_bins':40,'window_ms':30,'feature_step_ms':10,'inference_step_ms':30},
                'frontend_fingerprint':frontend_fingerprint(),'development_passed':True,'candidate_frozen_at':'fixture'}
            path=root/'wake-policy.json';path.write_text(json.dumps(policy));output=root/'header.hpp'
            result=subprocess.run([sys.executable,str(Path(__file__).with_name('check_wake_policy.py')),
                '--model',str(model),'--policy',str(path),'--output',str(output)],capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,0,result.stderr)
            header=output.read_text()
            self.assertIn('#define PIKOO_WAKE_MODEL_SHA256 "'+policy['model_sha256']+'"',header)
            self.assertIn('#define PIKOO_WAKE_POLICY_SHA256 "'+hashlib.sha256(path.read_bytes()).hexdigest()+'"',header)

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
            trial = {**dual, 'development_passed': False, 'trial_authorized': True,
                     'status': 'best-available-unqualified-trial',
                     'formal_goal_passed': False, 'release_eligible': False}
            with self.assertRaises(ValueError):
                validate(model, trial)
            self.assertFalse(validate(model, trial, allow_trial=True)['development_passed'])
            for key in ('trial_authorized', 'formal_goal_passed', 'release_eligible'):
                bad = {**trial, key: not trial[key]}
                with self.assertRaises(ValueError):
                    validate(model, bad, allow_trial=True)
