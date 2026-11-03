# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from wake_secondary_dev import sha, load, evaluate, complete_nihao


class SecondaryDevTest(unittest.TestCase):
    def fixture(self, root):
        sources = [f'source-{i}' for i in range(4)]
        speeds = [1., 1.15, 1.3, 1.5]
        arrays = {f'case_{i}': np.zeros((12, 40), np.float32) for i in range(16)}
        np.savez_compressed(root/'features.npz', **arrays)
        cases = [{'source_sha256': s, 'speed': v, 'original_split': 'validation',
                  'historical_label': 1, 'expected_current_contract_label': 0,
                  'whole_original_waveform_used': True, 'times_ms': [50, 80, 110, 140]}
                 for s in sources for v in speeds]
        protocol = {'source_sha256': sources, 'speeds': speeds,
            'selection': 'all four original validation files passing content screens, no KWS-score selection',
            'household_used': False, 'TEST_opened': False, 'fixed_policy': {'rolling': 3, 'threshold': .9}}
        reviews = [{'source_sha256': s, 'original_split': 'validation', 'original_speaker': 'dev-'+s,
            'prior_approved': True, 'v3_screen_agreement': True,
            'prior_transcript': '你好皮褲', 'local_transcript': '你好，皮裤。'} for s in sources]
        manifest = [{'sha256': s, 'speaker': 'dev-'+s, 'split': 'validation', 'label': 0,
            'historical_label': 1, 'synthetic': True} for s in sources]
        values = {'cases': cases, 'protocol': protocol, 'content_review': reviews,
                  'protected': [], 'source_manifest': manifest}
        spec = {'features': str(root/'features.npz'), 'features_sha256': sha(root/'features.npz')}
        for key, value in values.items():
            path = root/(key+'.json'); path.write_text(json.dumps(value))
            spec[key], spec[key+'_sha256'] = str(path), sha(path)
        return spec

    def change(self, spec, key, update):
        path = Path(spec[key]); value = json.loads(path.read_text()); update(value)
        path.write_text(json.dumps(value)); spec[key+'_sha256'] = sha(path)

    def test_complete_greeting_and_orthography_without_accepting_target_Hi(self):
        self.assertTrue(complete_nihao('你好，皮褲。'))
        self.assertTrue(complete_nihao('你好Piku'))
        for text in ('Hi Pikoo', '你好', '你好屁股', '你好皮Q'):
            self.assertFalse(complete_nihao(text))

    def test_source_roles_protection_and_full_cartesian_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); spec = self.fixture(root)
            self.assertEqual(len(load(spec)[0]), 16)
            with self.assertRaises(ValueError): load(spec, train_speakers={'dev-source-0'})
            self.change(spec, 'protected', lambda x: x.append('source-0'))
            with self.assertRaises(ValueError): load(spec)
            spec = self.fixture(root)
            self.change(spec, 'cases', lambda x: x.pop())
            with self.assertRaises(ValueError): load(spec)
            spec = self.fixture(root)
            self.change(spec, 'source_manifest', lambda x: x[0].update(split='test'))
            with self.assertRaises(ValueError): load(spec)
            spec = self.fixture(root)
            self.change(spec, 'content_review', lambda x: x[0].update(local_transcript='Hi Pikoo'))
            with self.assertRaises(ValueError): load(spec)

    def test_actual_new_model_scores_required_and_false_guard_blocks_finalization(self):
        class Fake:
            def __init__(self, fail): self.fail = fail
            def configure(self, model): pass
            def run(self, features, temporary):
                return np.full(4, .996 if self.fail else 0., np.float32), 38000
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); spec = self.fixture(root)
            model, micro = root/'model.bin', root/'micro.bin'
            model.write_bytes(b'new-model'); micro.write_bytes(b'pinned-runner')
            report = evaluate(model, micro, spec, root, evaluator=Fake(False))
            self.assertEqual(report['false_wakes'], 0)
            self.assertEqual(report['model_sha256'], sha(model))
            with self.assertRaisesRegex(ValueError, 'cannot be finalized'):
                evaluate(model, micro, spec, root, evaluator=Fake(True))
            self.assertEqual(json.loads((root/'secondary-negative-dev-report.json').read_text())['false_wakes'], 16)


if __name__ == '__main__': unittest.main()
