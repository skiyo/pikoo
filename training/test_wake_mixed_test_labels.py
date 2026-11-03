# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from wake_mixed_test import COHORTS, protocol
from wake_mixed_test_labels import assemble, record_label, seal


class HumanContentLabels(unittest.TestCase):
    def setUp(self):
        self.policy = {'target': 'hi-piku-piko-v2', 'development_passed': True,
            'source_native_freeze_sha256': 'native-fixture', 'micro_proof_sha256': 'parity-fixture',
            'required_test_cohorts': COHORTS, 'required_fresh_test_speakers': ['openai:echo', 'openai:shimmer'],
            'model_sha256': 'model-fixture', 'candidate_frozen_at': '2026-11-03T01:00:00+00:00',
            'rolling': 3, 'threshold': .9}
        self.plan = protocol(self.policy, 'policy-sha', 'protected-sha', '2026-11-03T02:00:00+00:00')
        self.row = {'id': 'TEST-041', 'status': 'recorded', 'sha256': 'audio-sha'}

    def test_incomplete_utterance_never_inherits_positive_prompt(self):
        draft = record_label(None, self.plan, 'protocol-sha', self.row,
            'hi-alone', 'adult', 'standard', True, True)
        label = draft['records'][0]
        self.assertEqual(label['actual_label'], 0)
        self.assertEqual(label['actual_variant'], 'non-target')
        self.assertEqual(label['negative_category'], 'hi-alone')
        self.assertFalse(label['complete_hi_and_name'])
        self.assertFalse(draft['model_scored'])

    def test_target_labels_need_endpoint_and_immutable_waveform_hash(self):
        for completion in (None, float('nan'), float('inf'), 0, -1):
            with self.subTest(completion=completion), self.assertRaises(ValueError):
                record_label(None, self.plan, 'protocol-sha', self.row,
                    'hi-piko', 'adult', 'standard', True, True, completion)
        draft = record_label(None, self.plan, 'protocol-sha', self.row,
            'hi-piko', 'adult', 'standard', True, True, 1200)
        with self.assertRaisesRegex(ValueError, 'Waveform replaced'):
            record_label(draft, self.plan, 'protocol-sha', {**self.row, 'sha256': 'changed'},
                'hi-piku', 'adult', 'standard', True, True, 1100)
        with self.assertRaises(ValueError):
            record_label(draft, self.plan, 'another-protocol', self.row,
                'hi-piku', 'adult', 'standard', True, True, 1100)

    def test_accepting_either_pronunciation_stays_positive_without_inventing_a_vowel(self):
        draft = record_label(None, self.plan, 'protocol-sha', self.row,
            'hi-piku-or-piko', 'adult', 'standard', True, True)
        label = draft['records'][0]
        self.assertEqual(label['actual_label'], 1)
        self.assertTrue(label['quality_valid'])
        self.assertTrue(label['complete_hi_and_name'])
        self.assertIsNone(label['actual_variant'])
        self.assertIsNone(label['negative_category'])
        self.assertEqual(label['pending_annotations'], ['actual_variant', 'completion_ms'])
        updated = record_label(draft, self.plan, 'protocol-sha', self.row,
            'hi-piku-or-piko', 'adult', 'standard', True, True, 1200)
        self.assertEqual(updated['records'][0]['pending_annotations'], ['actual_variant'])
        for invalid in (0, -1, float('nan'), float('inf')):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                record_label(None, self.plan, 'protocol-sha', self.row,
                    'hi-piku-or-piko', 'adult', 'standard', True, True, invalid)

    def test_assemble_preserves_all_missing_and_failed_slots_without_recording(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root/'synthetic').mkdir()
            recorded, failed = [s for s in self.plan['slots'] if s['source_kind']=='synthetic'][:2]
            audio = root/'synthetic/fixture.wav'; audio.write_bytes(b'generated-fixture-not-real-audio')
            rows = [dict(id=recorded['id'], status='recorded', speaker=recorded['speaker'],
                frozen_model_sha256='model-fixture', path='fixture.wav', sha256=hashlib.sha256(audio.read_bytes()).hexdigest()),
                dict(id=failed['id'], status='failed-source-generation', speaker=failed['speaker'], frozen_model_sha256='model-fixture')]
            (root/'synthetic/manifest.json').write_text(json.dumps(rows))
            result = assemble(self.plan, root)
            self.assertEqual(len(result), 150)
            self.assertEqual(sum(r['status']=='recorded' for r in result), 1)
            self.assertEqual(sum(r['status']=='failed-source-generation' for r in result), 1)
            self.assertEqual(sum(r['status']=='missing-not-captured' for r in result), 148)
            family = next(r for r in result if r['source_kind']=='family')
            with self.assertRaises(ValueError):
                record_label(None, self.plan, 'protocol-sha', family,
                    'hi-piko', 'child', 'Chinese-accent', True, True, 1000)

    def test_seal_refuses_partial_bundle_and_does_not_fill_missing_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = assemble(self.plan, root)
            draft = record_label(None, self.plan, 'protocol-sha', self.row,
                'hi-piko', 'adult', 'standard', True, True, 1200)
            with self.assertRaisesRegex(ValueError, 'Every attempt needs'):
                seal(self.plan, rows, draft, root, self.policy, 'policy-sha', set(),
                     'protected-sha', 'manifest-sha', 'protocol-sha')
            self.assertFalse((root/'human-review.json').exists())


if __name__ == '__main__': unittest.main()
