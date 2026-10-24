import copy
import unittest
from reassess_content import reassess, OLD_RULE
from clean_corpus import clean


class TranscriptReassessmentTest(unittest.TestCase):
    def setUp(self):
        self.row = dict(sha256='a'*64, split='train', label=0,
                        source='Google-Gemini-TTS-synthetic', synthetic=True,
                        text='你好皮克', group='fictional-training-voice')
        self.raw = dict(sha256='a'*64, label=0, transcript='你好，匹克。',
                        approved=False, model='gemini-3.1-flash-lite',
                        rule=OLD_RULE, diagnostic_only=False, admission_eligible=True)

    def test_known_spelling_defect_preserves_raw_and_label(self):
        before = copy.deepcopy(self.raw)
        derived = reassess(self.row, self.raw)
        self.assertEqual(self.raw, before)
        self.assertEqual(derived['prior_raw_observation'], before)
        self.assertEqual(derived['transcript'], before['transcript'])
        self.assertEqual(derived['label'], 0)
        self.assertTrue(derived['approved'])
        self.assertEqual(clean([self.row], [derived])[0], [self.row])

    def test_other_reliable_disagreement_still_quarantines(self):
        derived = reassess(self.row, self.raw)
        other = {**self.raw, 'transcript': '你好皮酷'}
        self.assertEqual(clean([self.row], [derived, other])[0], [])

    def test_ambiguous_partial_extra_words_and_targets_cannot_be_reassessed(self):
        for text in ['你好皮酷', '你好 P库', '你好Pico', '你好Pku', '你好Pi',
                     '匹克', '你好匹克 hello', '你好匹克 123', '你好屁股']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                reassess(self.row, {**self.raw, 'transcript': text})
        for change in [dict(split='validation'), dict(split='test'), dict(label=1),
                       dict(source='ChildMandarin'), dict(synthetic=False),
                       dict(family_inputs_used=True), dict(real_child=True),
                       dict(reference_audio_used=True), dict(frozen_holdout=True)]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                reassess({**self.row, **change}, self.raw)

    def test_contextual_legacy_changed_identity_or_prior_failures_stop(self):
        for change in [dict(diagnostic_only=True), dict(admission_eligible=False),
                       dict(rule='unknown'), dict(sha256='b'*64), dict(label=1),
                       dict(model='qwen-asr'), dict(prior_approved=False),
                       dict(local_approved=False), dict(approved=True)]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                reassess(self.row, {**self.raw, **change})


if __name__ == '__main__':
    unittest.main()
