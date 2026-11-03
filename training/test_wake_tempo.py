# SPDX-License-Identifier: Apache-2.0
import json
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest

import numpy as np
from wake_tempo import stretch, source_rows, apply_gate, preservation_cases, variants, verify_dev_reference, prepare


class TempoTest(unittest.TestCase):
    def test_legacy_acoustic_cache_cannot_silently_keep_post_noise_clock(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp)/'config.json'
            config.write_text(json.dumps({'method': 'ffmpeg-atempo-pitch-preserving',
                'factors': [1.15, 1.3, 1.5], 'TRAIN_only_augmentation': True,
                'TRAIN_continuous_variants_per_source': 6, 'TRAIN_acoustic_augmentation': True}))
            with self.assertRaisesRegex(ValueError, 'v2 clean-reference'):
                prepare(None, None, None, None, None, None, None, None, None, config, Path(tmp))

    def test_fixed_DEV_reference_rejects_feature_or_clock_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); x = np.zeros((1, 6, 40), np.float32)
            meta = [{'sha256': 'dev', 'completion_ms': 400}]
            np.savez_compressed(root/'dev-features.npz', x=x)
            (root/'dev-metadata.json').write_text(json.dumps(meta))
            digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
            (root/'provenance.json').write_text(json.dumps({'files_sha256': {
                name: digest(root/name) for name in ('dev-features.npz', 'dev-metadata.json')}}))
            provenance = digest(root/'provenance.json')
            verify_dev_reference(x, [{**meta[0], 'acoustic_augmentation': False}], root, provenance)
            with self.assertRaises(ValueError): verify_dev_reference(x+1, meta, root, provenance)
            with self.assertRaises(ValueError):
                verify_dev_reference(x, [{**meta[0], 'completion_ms': 300}], root, provenance)

    def test_continuous_TRAIN_is_banded_seeded_and_does_not_change_DEV(self):
        fixed = {'factors': [1.15, 1.3, 1.5]}
        config = {**fixed, 'TRAIN_continuous_variants_per_source': 6, 'TRAIN_acoustic_augmentation': True}
        train = {'sha256': 'train', 'split': 'train'}
        first = variants(train, config)
        self.assertEqual(first, variants(train, config))
        self.assertEqual(len(first), 6)
        for i, (rate, key, acoustic) in enumerate(first):
            lo, hi = ((1, 1.15), (1.15, 1.3), (1.3, 1.5))[i % 3]
            self.assertTrue(lo < rate < hi)
            self.assertTrue(acoustic)
        dev = {'sha256': 'dev', 'split': 'validation'}
        self.assertEqual(variants(dev, fixed), variants(dev, config))
        self.assertFalse(any(acoustic for _, _, acoustic in variants(dev, config)))
        with self.assertRaises(ValueError): variants(train, {**config, 'TRAIN_acoustic_augmentation': False})

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
