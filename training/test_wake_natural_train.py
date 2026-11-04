# SPDX-License-Identifier: Apache-2.0
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from wake_natural_train import load_context, validate_natural_row


class NaturalTrainAdmission(unittest.TestCase):
    def fixture(self, label=1):
        original = {'sha256': 'original', 'speaker': 'TRAIN-family', 'text': 'Hi Pikoo' if label else 'Hi Tikoo',
                    'label': label, 'split': 'train', 'source': 'Qwen3-TTS-hi-piku-synthetic-local',
                    'path': 'audio.wav', 'audition_only': False, 'purpose': 'TRAIN-candidate-quarantine',
                    'real_child': False, 'reference_audio_used': False, 'family_inputs_used': False,
                    'synthetic': True}
        row = {**original, 'perceived_style': 'childlike', 'synthetic_style': 'childlike',
               'perceived_style_review': 'passed', 'per_record_human_audition': True,
               'human_review_sha256': 'human', 'raw_manifest_sha256': 'raw',
               'target_contract': 'hi-piku-piko-v2', 'content_review': 'passed',
               'pronunciation_review': 'passed', 'admitted_to_training': True}
        verdict = {'source_sha256': 'original', 'approved_for_TRAIN': True, 'human_content_correct': True,
                   'original_binary_label': label, 'expected_text': row['text'], 'source_family': row['speaker'],
                   'human_actual_perceived_style': 'childlike'}
        context = {'declaration': {'human_feedback_sha256': 'human', 'raw_manifest_sha256': 'raw'},
                   'originals': {'original': original}, 'feedback': {'original': verdict},
                   'sources': {'TRAIN-family'}, 'never_train': set()}
        return row, context

    def test_unknown_rejected_or_protected_partner_prevents_single_original_admission(self):
        row, context = self.fixture()
        partner = {**context['originals']['original'], 'sha256': 'partner', 'label': 0, 'text': 'Hi Tikoo'}
        context['originals']['partner'] = partner
        context['matched_pairs'] = {'original': 'partner', 'partner': 'original'}
        verdict = {**context['feedback']['original'], 'source_sha256': 'partner',
                   'original_binary_label': 0, 'expected_text': 'Hi Tikoo'}
        with self.assertRaisesRegex(ValueError, 'Both matched'):
            validate_natural_row(row, context, set())
        context['feedback']['partner'] = verdict
        validate_natural_row(row, context, set())
        for field, value in [('approved_for_TRAIN', False), ('human_content_correct', None),
                             ('human_actual_perceived_style', 'unverified'),
                             ('expected_text', 'Hi Pikoo'), ('source_family', 'different')]:
            changed = copy.deepcopy(context); changed['feedback']['partner'][field] = value
            with self.assertRaisesRegex(ValueError, 'Both matched'):
                validate_natural_row(row, changed, set())
        context['never_train'].add('partner')
        with self.assertRaisesRegex(ValueError, 'Both matched'):
            validate_natural_row(row, context, set())

    def test_explicit_positive_and_T_negative_can_pass_without_ASR_agreement(self):
        for label in (0, 1):
            row, context = self.fixture(label)
            validate_natural_row(row, context, {'DEV-family'})

    def test_prompt_age_or_partial_content_approval_cannot_admit(self):
        row, context = self.fixture()
        for field, value in [('approved_for_TRAIN', False), ('human_content_correct', None),
                             ('human_actual_perceived_style', 'unverified'),
                             ('human_actual_perceived_style', 'adolescent'),
                             ('original_binary_label', 0), ('source_family', 'different'),
                             ('expected_text', 'Hi Tikoo')]:
            changed = copy.deepcopy(context)
            changed['feedback']['original'][field] = value
            with self.assertRaises(ValueError): validate_natural_row(row, changed, set())

    def test_auditions_protected_or_DEV_sources_never_enter(self):
        row, context = self.fixture()
        with self.assertRaises(ValueError): validate_natural_row(row, context, {'TRAIN-family'})
        with self.assertRaises(ValueError): validate_natural_row(row, None, set())
        for field, value in [('audition_only', True), ('purpose', 'source-audition-only-never-training'),
                             ('family_inputs_used', True), ('reference_audio_used', True),
                             ('real_child', True), ('frozen_holdout', True), ('parent_sha256', 'parent')]:
            changed = copy.deepcopy(context); changed['originals']['original'][field] = value
            with self.assertRaises(ValueError): validate_natural_row(row, changed, set())
        changed = copy.deepcopy(context); changed['never_train'].add('original')
        with self.assertRaises(ValueError): validate_natural_row(row, changed, set())

    def test_labels_paths_and_review_hashes_cannot_change(self):
        row, context = self.fixture()
        for field, value in [('label', 0), ('text', 'Hi Tikoo'), ('path', 'another.wav'),
                             ('split', 'validation'), ('speaker', 'another'),
                             ('human_review_sha256', 'changed'), ('raw_manifest_sha256', 'changed'),
                             ('perceived_style', 'adult'), ('per_record_human_audition', False)]:
            with self.assertRaises(ValueError): validate_natural_row({**row, field: value}, context, set())

    def test_evidence_bound_to_files_and_explicit_nonfamily_TRAIN_review(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); row, context = self.fixture()
            feedback = {'scope': 'per-record-human-synthetic-TRAIN-content-and-style',
                        'per_record_human_listening': True, 'household_used': False, 'DEV_used': False,
                        'TEST_opened': False, 'wake_scores_used_for_selection': False, 'labels_changed': False,
                        'rows': list(context['feedback'].values())}
            files = {'raw_manifest': list(context['originals'].values()), 'human_feedback': feedback,
                     'source_reservation': {'source_SPLIT': 'TRAIN-only reserved before generation; neverfutureTEST',
                         'household_used': False, 'TEST_opened': False, 'source_families': ['TRAIN-family']},
                     'never_train': {'audio_sha256': {'audition': 'excluded'}}}
            declaration = {'original_manifest_sha256': 'base'}
            def write(name):
                p = root/(name+'.json'); p.write_text(json.dumps(files[name]))
                declaration[name+'_file'] = p.name
                declaration[name+'_sha256'] = hashlib.sha256(p.read_bytes()).hexdigest()
            for name in files: write(name)
            review = {'human_natural_admission': declaration}
            self.assertIsNone(load_context({}, root/'review.json', 'base'))
            self.assertEqual(load_context(review, root/'review.json', 'base')['never_train'], {'excluded'})
            files['source_reservation']['matched_pair_review_required'] = True; write('source_reservation')
            with self.assertRaisesRegex(ValueError, 'requires hashed pair'):
                load_context(review, root/'review.json', 'base')
            partner = {**files['raw_manifest'][0], 'sha256': 'partner', 'label': 0, 'text': 'Hi Tikoo'}
            files['raw_manifest'].append(partner); write('raw_manifest')
            files['matched_pairs'] = [{'positive_sha256': 'original', 'negative_sha256': 'partner'}]
            write('matched_pairs')
            self.assertEqual(load_context(review, root/'review.json', 'base')['matched_pairs'],
                             {'original': 'partner', 'partner': 'original'})
            for pairs in ([], files['matched_pairs']*2,
                          [{'positive_sha256': 'original', 'negative_sha256': 'missing'}],
                          [{'positive_sha256': 'partner', 'negative_sha256': 'original'}]):
                saved = files['matched_pairs']; files['matched_pairs'] = pairs; write('matched_pairs')
                with self.assertRaises(ValueError): load_context(review, root/'review.json', 'base')
                files['matched_pairs'] = saved
            write('matched_pairs')
            (root/'matched_pairs.json').write_text('tampered')
            with self.assertRaises(ValueError): load_context(review, root/'review.json', 'base')
            write('matched_pairs')
            with self.assertRaises(ValueError): load_context(review, root/'review.json', 'other')
            for field in ('household_used', 'DEV_used', 'TEST_opened', 'wake_scores_used_for_selection', 'labels_changed'):
                feedback[field] = True; write('human_feedback')
                with self.assertRaises(ValueError): load_context(review, root/'review.json', 'base')
                feedback[field] = False
            write('human_feedback')
            feedback['rows'].append(copy.deepcopy(feedback['rows'][0])); write('human_feedback')
            with self.assertRaises(ValueError): load_context(review, root/'review.json', 'base')
            feedback['rows'].pop(); write('human_feedback')
            (root/'human_feedback.json').write_text('changed')
            with self.assertRaises(ValueError): load_context(review, root/'review.json', 'base')
            declaration['human_feedback_file'] = '../outside.json'
            with self.assertRaises(ValueError): load_context(review, root/'review.json', 'base')


if __name__ == '__main__': unittest.main()
