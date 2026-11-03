# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import numpy as np
from wake_tempo import stretch, source_rows, apply_gate, preservation_cases


class TempoTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg required for real pitch-preservation test')
    def test_acceleration_shortens_signal_without_transposing_fundamental(self):
        rate = 16000
        x = 8000*np.sin(2*np.pi*440*np.arange(rate*2)/rate)
        y = stretch(x, 1.5, Path(shutil.which('ffmpeg')))
        self.assertLess(abs(len(y)-len(x)/1.5), rate*.05)
        middle = y[1600:-1600]
        frequencies = np.fft.rfftfreq(len(middle), 1/rate)
        fundamental = frequencies[np.argmax(abs(np.fft.rfft(middle*np.hanning(len(middle)))))]
        self.assertLess(abs(fundamental-440), 3)  # resampling would transpose to 660Hz

    def test_invalid_tempo_rejected_before_backend_call(self):
        for factor in (0, 1, 1.6, float('nan')):
            with self.assertRaises(ValueError): stretch(np.ones(1000), factor, Path('/missing'))

    def test_new_gate_cannot_be_bypassed_by_old_qualification(self):
        old = {'qualified': True, 'selection_score': 1000.001}
        result = apply_gate(old, {'qualified': False, 'failure_penalty': 3})
        self.assertFalse(result['qualified'])
        self.assertAlmostEqual(result['selection_score'], -2.999)
        self.assertTrue(old['qualified'])
        self.assertFalse(apply_gate({'qualified': False, 'selection_score': -1},
                                   {'qualified': True, 'failure_penalty': 0})['qualified'])

    def rows(self):
        def row(digest, split, label, speaker):
            return {'sha256': digest, 'split': split, 'label': label, 'speaker': speaker,
                'synthetic': True, 'admitted_to_training': True, 'content_review': 'passed',
                'pronunciation_review': 'passed', 'target_contract': 'hi-piku-piko-v2'}
        return [row('train', 'train', 1, 'train-speaker'),
                row('dev+', 'validation', 1, 'dev-speaker'), row('dev-', 'validation', 0, 'dev-speaker')]

    def check_rows(self, rows, protected=()):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp)/'manifest.json'; manifest.write_text(json.dumps(rows))
            return source_rows(manifest, None, {'train'}, set(protected))

    def test_partitioned_originals_keep_split_and_reject_protected_audio(self):
        self.assertEqual(len(self.check_rows(self.rows())), 3)
        for field in ('family_inputs_used', 'evaluation_only', 'frozen_holdout', 'reference_audio_used'):
            rows = self.rows(); rows[0][field] = True
            with self.assertRaises(ValueError): self.check_rows(rows)
        with self.assertRaises(ValueError): self.check_rows(self.rows(), {'train'})

    def test_source_speaker_cannot_cross_split_and_TEST_is_never_admitted(self):
        rows = self.rows(); rows[1]['speaker'] = 'train-speaker'
        with self.assertRaises(ValueError): self.check_rows(rows)
        rows = self.rows(); rows[1]['split'] = 'test'
        with self.assertRaises(ValueError): self.check_rows(rows)

    def test_donor_preservation_requires_identical_DEV_cases_and_provenance(self):
        from hi_pikoo_model import policy_metrics
        case = {'sha256': 'dev', 'label': 1, 'cohort': 'adult:standard:piku',
                'valid_steps': 3, 'completion_ms': 60, 'times_ms': [0, 30, 60],
                'probabilities': [.99, .99, .99]}
        proof = {'household_used': False, 'TEST_opened': False, 'old_DEV': policy_metrics([case], 3, .9)}
        original = {**case, 'probabilities': [0, 0, 0]}
        self.assertEqual(preservation_cases([original], [case], proof), [case])
        with self.assertRaises(ValueError):
            preservation_cases([{**original, 'completion_ms': 90}], [case], proof)
        with self.assertRaises(ValueError):
            preservation_cases([original], [case], {**proof, 'household_used': True})


if __name__ == '__main__': unittest.main()
