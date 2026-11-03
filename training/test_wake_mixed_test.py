# SPDX-License-Identifier: Apache-2.0
"""Generated fixture PCM only: no household, provider or inference access."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import wave

from wake_mixed_test import COHORTS, protocol, validate_bundle, protection_snapshot, timestamp
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from wake_test_capture import decode_capture


class MixedTestIsolation(unittest.TestCase):
    def test_JS_UTC_Z_and_offset_timestamps_are_equal_and_naive_is_rejected(self):
        self.assertEqual(timestamp('2026-11-03T09:34:54.881Z'),
                         timestamp('2026-11-03T09:34:54.881+00:00'))
        self.assertEqual(timestamp('2026-11-03T09:34:54.881Z'),
                         timestamp('2026-11-03T17:34:54.881+08:00'))
        with self.assertRaisesRegex(ValueError,'Timezone-aware'):
            timestamp('2026-11-03T09:34:54.881')

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.policy = {'target': 'hi-piku-piko-v2', 'development_passed': True,
            'source_native_freeze_sha256': 'native-fixture', 'micro_proof_sha256': 'parity-fixture',
            'required_test_cohorts': COHORTS, 'required_fresh_test_speakers': ['openai:echo', 'openai:shimmer'],
            'model_sha256': 'model-fixture', 'candidate_frozen_at': '2026-11-03T01:00:00+00:00',
            'rolling': 3, 'threshold': .9}
        cls.plan = protocol(cls.policy, 'policy-sha', 'protected-sha', '2026-11-03T02:00:00+00:00')
        cls.rows, records = [], []
        for i, slot in enumerate(cls.plan['slots']):
            family = slot['source_kind'] == 'family'
            pcm = (i + 1).to_bytes(2, 'little') * (64000 if family else 16000)
            folder = cls.root / slot['id']; folder.mkdir()
            path = folder / 'TEST.wav'
            with wave.open(str(path), 'wb') as audio:
                audio.setparams((1, 2, 16000, 0, 'NONE', 'not compressed')); audio.writeframes(pcm)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            row = {'id': slot['id'], 'status': 'recorded', 'split': 'test',
                'evaluation_only': True, 'frozen_holdout': True, 'training_or_tuning_allowed': False,
                'model_scored': False, 'cloud_uploaded': False, 'source_audition': False,
                'speaker': slot['speaker'], 'source_kind': slot['source_kind'],
                'frozen_model_sha256': 'model-fixture', 'created_at': '2026-11-03T03:00:04+00:00',
                'path': str(path.relative_to(cls.root)), 'sha256': digest,
                'synthetic': not family, 'real_child': slot['role'] == 'child',
                'family_inputs_used': family, 'reference_audio_used': False}
            if family:
                def diag(uptime):
                    return ('diag: board=fixture state=0 muted=0 upload=0 uploaded_samples=0 '
                            f'frames=0 reconnects=0 uptime_ms={uptime} wake_errors=0 wake_dropped=0')
                payload = base64.b64encode(pcm[:320]).decode()
                raw = '\n'.join([diag(10000), 'wake_pcm: begin rate=16000 samples=64000',
                    *(f'wake_pcm: seq={j} count=160 data={payload}' for j in range(400)),
                    'wake_pcm: done', diag(15000)]).encode()
                _, proof = decode_capture(raw); proof['old_model_scores_ignored'] = True
                (folder / 'capture.log').write_bytes(raw)
                capture = {'status': 'captured-unlabelled-not-scored', 'speaker_id': slot['speaker'],
                    'test_slot_id': slot['id'], 'protocol_sha256': 'protocol-sha',
                    'speaker_role_user_declared': slot['role'], 'prompt': slot['prompt'],
                    'model_sha256': 'model-fixture', 'policy_sha256': 'policy-sha',
                    'split': 'test', 'evaluation_only': True, 'frozen_holdout': True,
                    'synthetic': False, 'real_child': slot['role'] == 'child', 'family_inputs_used': True,
                    'training_or_tuning_allowed': False, 'model_scored': False, 'actual_content_label': None,
                    'started_at': '2026-11-03T03:00:00+00:00', 'completed_at': row['created_at'], 'transport': proof}
                (folder / 'capture.json').write_text(json.dumps(capture))
                row['capture_metadata_path'] = str((folder / 'capture.json').relative_to(cls.root))
            cls.rows.append(row)
            records.append({'id': slot['id'], 'sha256': digest, 'quality_valid': True,
                'reviewed_at': '2026-11-03T04:00:00+00:00',
                'actual_label': slot['expected_label'], 'actual_age': slot['role'],
                'actual_accent': slot['accent'], 'no_repetition_or_extra_words': True,
                'actual_variant': slot['prompt'].split()[1] if slot['expected_label'] else 'non-target',
                'complete_hi_and_name': bool(slot['expected_label']), 'completion_ms': 900,
                'negative_category': slot.get('negative_category')})
        cls.review = {'protocol_sha256': 'protocol-sha', 'manifest_sha256': 'manifest-sha',
            'model_sha256': 'model-fixture', 'policy_sha256': 'policy-sha',
            'labels_committed_before_model_scores': True, 'model_scored': False,
            'reviewed_by': 'human-content-only', 'reviewed_at': '2026-11-03T04:00:00+00:00',
            'records': records}

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def validate(self, **changes):
        arguments = dict(plan=self.plan, rows=self.rows, review=self.review, root=self.root,
            policy=self.policy, policy_sha256='policy-sha', protected=set(),
            protected_sha256='protected-sha', manifest_sha256='manifest-sha', protocol_sha256='protocol-sha')
        arguments.update(changes)
        return validate_bundle(**arguments)

    def test_fixed_full_scope_generated_fixture_validates_without_scoring(self):
        verified = self.validate()
        self.assertEqual(len(verified), 150)
        self.assertEqual(sum(r['role'] == 'child' for r in verified), 40)
        self.assertEqual(sum(r['source_kind'] == 'family' for r in verified), 80)

    def test_missing_and_duplicate_attempts_cannot_be_silently_excluded(self):
        for rows in (self.rows[:-1], self.rows[:-1] + [self.rows[0]]):
            with self.assertRaisesRegex(ValueError, 'Complete fixed TEST'):
                self.validate(rows=rows)

    def test_changed_policy_plan_or_protection_cannot_score(self):
        plan = copy.deepcopy(self.plan); plan['fixed_policy']['threshold'] = .85
        with self.assertRaises(ValueError): self.validate(plan=plan)
        with self.assertRaises(ValueError): self.validate(policy_sha256='another')
        with self.assertRaises(ValueError): self.validate(protected={self.rows[0]['sha256']})

    def test_consumed_audition_train_and_predeclared_date_guards(self):
        for change in ({'split': 'train'}, {'source_audition': True}, {'model_scored': True},
                       {'cloud_uploaded': True}, {'created_at': '2026-11-03T01:30:00+00:00'},
                       {'parent_sha256': 'old'}, {'training_or_tuning_allowed': True},
                       {'path': '../escape.wav'}):
            rows = copy.deepcopy(self.rows); rows[0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.validate(rows=rows)

    def test_bad_child_age_missing_name_and_actual_vowel_coverage_do_not_pass(self):
        child = next(i for i, s in enumerate(self.plan['slots']) if s['role'] == 'child')
        for index, change in ((child, {'actual_age': 'adult'}),
                              (0, {'complete_hi_and_name': False}),
                              (0, {'actual_variant': 'piku' if self.review['records'][0]['actual_variant']=='piko' else 'piko'}),
                              (0, {'completion_ms': float('nan')}),
                              (149, {'actual_variant': 'piko'})):
            review = copy.deepcopy(self.review); review['records'][index].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.validate(review=review)

    def test_review_must_cover_all_cases_and_precede_model_predictions(self):
        for change in ({'model_scored': True}, {'labels_committed_before_model_scores': False},
                       {'records': self.review['records'][:-1]}, {'reviewed_at': '2026-11-03T02:30:00+00:00'}):
            with self.subTest(change=list(change)), self.assertRaises(ValueError):
                self.validate(review={**self.review, **change})
        for stamp in ('2026-11-03T02:30:00+00:00', '2026-11-03T05:00:00+00:00'):
            review = copy.deepcopy(self.review); review['records'][0]['reviewed_at'] = stamp
            with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                self.validate(review=review)

    def test_family_transport_success_flag_cannot_override_modified_pcm_log(self):
        row = next(r for r in self.rows if r['source_kind'] == 'family')
        path = self.root / Path(row['capture_metadata_path']).parent / 'capture.log'
        saved = path.read_bytes()
        try:
            path.write_bytes(saved.replace(b'seq=12 ', b'seq=11 '))
            with self.assertRaisesRegex(ValueError, 'Missing/duplicate'):
                self.validate()
        finally: path.write_bytes(saved)

    def test_same_filename_manifests_do_not_overwrite_prior_hashes(self):
        with tempfile.TemporaryDirectory() as root:
            paths = []
            for i in range(2):
                directory = Path(root) / str(i); directory.mkdir()
                path = directory / 'manifest.json'
                path.write_text(json.dumps([{'sha256': str(i) * 64}]))
                paths.append(path)
            snapshot = protection_snapshot([], paths)
            self.assertEqual(set(snapshot['audio_sha256'].values()), {'0'*64, '1'*64})
            self.assertEqual(len(snapshot['source_metadata_sha256']), 2)

    def test_native_trace_truncation_and_reset_difference_rejected(self):
        from wake_mixed_test_score import checked_trace
        self.assertEqual(list(checked_trace(bytes([1, 2]*3), 2)), [1, 2])
        for raw in (bytes([1, 2]*3)[:-1], bytes([1, 2, 1, 2, 1, 3])):
            with self.assertRaises(ValueError): checked_trace(raw, 2)


if __name__ == '__main__': unittest.main()
