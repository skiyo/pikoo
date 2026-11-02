# SPDX-License-Identifier: Apache-2.0
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from hi_pikoo_review import validate
from wake_catalog_train import load_context, validate_catalog_row


class CatalogTrainAdmission(unittest.TestCase):
    def row_and_context(self):
        row = {'id': 'adult-1', 'sha256': 'waveform', 'source': 'Google-Gemini-TTS-prebuilt',
               'split': 'train', 'speaker': 'google-prebuilt:adult-voice',
               'provider_voice_id': 'adult-voice', 'label': 1, 'synthetic_style': 'adult',
               'accent': 'standard', 'perceived_style_review': 'provider-catalog-adult-only',
               'per_record_human_audition': True, 'human_review_sha256': 'human',
               'source_isolation_sha256': 'isolation', 'pronunciation_variant': 'piko',
               'target_contract': 'hi-piku-piko-v2', 'content_review': 'passed',
               'pronunciation_review': 'passed', 'admitted_to_training': True}
        context = {'declaration': {'human_feedback_sha256': 'human', 'source_isolation_sha256': 'isolation'},
                   'voices': {'adult-voice': {'type': 'prebuilt', 'language_code': 'en-US',
                                            'description': 'Adult catalog voice'}},
                   'feedback': {'waveform': {'source_id': 'adult-1', 'accepted': True, 'heard_variant': 'piko'}}}
        return row, context

    def test_human_heard_variant_wins_over_requested_variant(self):
        row, context = self.row_and_context()
        row['requested_variant'] = 'piku'
        validate_catalog_row(row, context, {'existing-train'}, {'existing-dev'})
        row['pronunciation_variant'] = 'piku'
        with self.assertRaises(ValueError): validate_catalog_row(row, context, set(), set())

    def test_source_leakage_unreviewed_and_DEV_review_cannot_admit(self):
        row, context = self.row_and_context()
        for train, dev in [({row['speaker']}, set()), (set(), {row['speaker']})]:
            with self.assertRaises(ValueError): validate_catalog_row(row, context, train, dev)
        for field, value in [('split', 'validation'), ('label', 0), ('synthetic_style', 'childlike'),
                             ('human_review_sha256', 'different'), ('per_record_human_audition', False),
                             ('pronunciation_variant', 'tikoo'), ('admitted_to_training', False)]:
            changed = {**row, field: value}
            with self.assertRaises(ValueError): validate_catalog_row(changed, context, set(), set())
        changed = copy.deepcopy(context)
        changed['feedback']['waveform']['original_DEV_index'] = 21
        with self.assertRaises(ValueError): validate_catalog_row(row, changed, set(), set())
        with self.assertRaises(ValueError): validate_catalog_row(row, None, set(), set())

    def test_catalog_screen_keeps_privacy_protection_and_original_hash_checks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); audio = root/'source.wav'; audio.write_bytes(b'fixture')
            digest = hashlib.sha256(audio.read_bytes()).hexdigest()
            row = {'source': 'Google-Gemini-TTS-prebuilt', 'synthetic': True,
                   'sha256': digest, 'split': 'train', 'path': audio.name}
            self.assertEqual(validate(row, root, set()), audio.resolve())
            with self.assertRaises(ValueError): validate(row, root, {digest})
            for field in ('family_inputs_used', 'reference_audio_used', 'real_child', 'evaluation_only', 'frozen_holdout'):
                with self.assertRaises(ValueError): validate({**row, field: True}, root, set())
            with self.assertRaises(ValueError): validate({**row, 'parent_sha256': 'parent'}, root, set())

    def test_context_is_bound_to_human_and_historical_source_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            def write(name, data):
                p = root/name; p.write_text(json.dumps(data)); return hashlib.sha256(p.read_bytes()).hexdigest()
            original_sha = write('base.json', [])
            isolation = {'used_voice_ID_collision': False,
                         'source_manifests_sha256': {str(root/'base.json'): original_sha},
                         'selected': [{'id': 'adult-voice'}]}
            feedback = {'household_recordings_used': False, 'TEST_opened': False,
                        'wake_scores_used_for_selection': False, 'records': []}
            declaration = {'source_isolation_file': 'isolation.json',
                           'source_isolation_sha256': write('isolation.json', isolation),
                           'human_feedback_file': 'human.json',
                           'human_feedback_sha256': write('human.json', feedback)}
            review = {'human_catalog_admission': declaration}
            self.assertIsNotNone(load_context(review, root/'review.json', original_sha))
            (root/'base.json').write_text('changed')
            with self.assertRaises(ValueError): load_context(review, root/'review.json', original_sha)
            write('base.json', [])
            feedback['TEST_opened'] = True
            declaration['human_feedback_sha256'] = write('human.json', feedback)
            with self.assertRaises(ValueError): load_context(review, root/'review.json', original_sha)
            declaration['human_feedback_file'] = '../human.json'
            with self.assertRaises(ValueError): load_context(review, root/'review.json', original_sha)


if __name__ == '__main__': unittest.main()
