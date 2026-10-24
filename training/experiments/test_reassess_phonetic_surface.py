import copy
import unittest
from reassess_phonetic_surface import reassess


class PhoneticSurfaceTest(unittest.TestCase):
    def setUp(self):
        self.row = dict(sha256='a'*64, split='train', label=1,
                        source='Qwen3-TTS-synthetic-local', synthetic=True,
                        real_child=False, family_inputs_used=False,
                        reference_audio_used=False, english_phonetic_surface=True,
                        text='Ni hao, pee coo.', expected_spoken_transcript='你好皮酷')
        self.raw = dict(sha256='a'*64, label=1, transcript='你好Piku', approved=False,
                        model='gemini-3.1-flash-lite', diagnostic_only=False,
                        admission_eligible=True,
                        rule='exact-transcript-with-target-homophones-v3-no-extra-Latin')
        self.local = dict(sha256='a'*64, label=1, transcript='Nihao Piku.',
                          approved=True, local_approved=True,
                          model='qwen3-asr-0.6b-4bit')

    def apply(self, row=None, raw=None, local=None, protected=None):
        return reassess(self.row if row is None else row,
                        self.raw if raw is None else raw,
                        [self.local] if local is None else local,
                        set() if protected is None else protected)

    def test_corrects_only_assessment_and_preserves_raw(self):
        before = copy.deepcopy((self.row,self.raw,self.local))
        derived = self.apply()
        self.assertTrue(derived['approved'])
        self.assertEqual(derived['prior_raw_observation'], self.raw)
        self.assertEqual(derived['transcript'], self.raw['transcript'])
        self.assertEqual(before, (self.row,self.raw,self.local))

    def test_protected_non_train_or_missing_provenance_rejected(self):
        with self.assertRaises(ValueError): self.apply(protected={'a'*64})
        for delta in [dict(split='validation'),dict(label=0),dict(real_child=True),
                      dict(family_inputs_used=True),dict(reference_audio_used=True),
                      dict(real_child=None),dict(synthetic=False),dict(frozen_holdout=True),
                      dict(english_phonetic_surface=False),dict(text='你好Pikoo'),
                      dict(expected_spoken_transcript='你好皮克'),
                      dict(parent_sha256='b'*64),dict(ancestry_parents=['b'*64])]:
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                self.apply(row=dict(self.row,**delta))

    def test_incomplete_near_word_and_extra_speech_rejected(self):
        for heard in ['你好皮','你好Tikoo','你好皮克','你好屁股','Hello 你好Piku',
                      '你好Piku2','Piku','你好Pikuありがとう']:
            with self.subTest(heard=heard), self.assertRaises(ValueError):
                self.apply(raw=dict(self.raw,transcript=heard))

    def test_diagnostic_identity_and_prior_disagreement_rejected(self):
        for delta in [dict(diagnostic_only=True),dict(admission_eligible=False),
                      dict(sha256='b'*64),dict(label=0),dict(prior_approved=False),
                      dict(local_approved=False),dict(approved=True),dict(rule='legacy')]:
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                self.apply(raw=dict(self.raw,**delta))

    def test_local_corroboration_required_and_no_disagreement_erased(self):
        for records in [[],[dict(self.local,approved=False)],
                        [dict(self.local,transcript='你好皮克')],
                        [dict(self.local,sha256='b'*64)],
                        [self.local,dict(self.local,prior_approved=False)]]:
            with self.subTest(records=records), self.assertRaises(ValueError):
                self.apply(local=records)


if __name__ == '__main__': unittest.main()
