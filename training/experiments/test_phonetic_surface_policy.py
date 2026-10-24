import unittest
from unittest.mock import patch
from phonetic_surface_policy import content_approved
from review_local_corpus import content_approved as original
from clean_corpus import clean
from reassess_phonetic_surface import reassess, OLD_RULE


class PhoneticBoundaryPolicyTest(unittest.TestCase):
    def setUp(self):
        self.row = dict(sha256='a'*64, split='train', label=1,
                        source='Qwen3-TTS-synthetic-local', synthetic=True,
                        real_child=False, family_inputs_used=False,
                        reference_audio_used=False, english_phonetic_surface=True,
                        text='Ni hao, pee coo.', expected_spoken_transcript='你好皮酷',
                        group='fictional-train-prompt')
        self.raw = dict(sha256='a'*64, label=1, transcript='你好Piku', approved=False,
                        model='gemini-3.1-flash-lite', diagnostic_only=False,
                        admission_eligible=True, rule=OLD_RULE)
        self.local = dict(sha256='a'*64, label=1, transcript='Nihao Piku.',
                          approved=True, local_approved=True, model='qwen3-asr-0.6b-4bit')

    def test_chinese_english_adjacency_is_the_documented_defect(self):
        self.assertFalse(original(self.row, '你好Piku'))
        for text in ['你好Piku','你好Pikoo','你好Pee Koo','Nihao Piku.',
                     'Ni hao! Pee coo!', '你好皮酷']:
            with self.subTest(text=text): self.assertTrue(content_approved(self.row,text))

    def test_incomplete_near_words_and_extra_text_stay_rejected(self):
        for text in ['你好皮','你好Tikoo','你好皮克','你好屁股','你好Pico',
                     '你好Piku2','xPiku','Hello你好Piku','NihaoXPiku',
                     '你好Pikoo hello','你好Pikuありがとう']:
            with self.subTest(text=text): self.assertFalse(content_approved(self.row,text))

    def test_nonphonetic_rules_unchanged(self):
        for row in [dict(self.row,english_phonetic_surface=False,text='你好Pikoo'),
                    dict(self.row,english_phonetic_surface=False,label=0,text='你好皮克')]:
            for heard in ['你好皮酷','你好匹克','你好Piku','你好Pi','你好Piku hello']:
                self.assertEqual(content_approved(row,heard),original(row,heard))

    def test_cleaner_requires_versioned_assessment_and_all_other_evidence(self):
        derived = reassess(self.row,self.raw,[self.local],set())
        # The running default remains conservative until an explicit versioned integration.
        self.assertEqual(clean([self.row],[self.local,derived])[0],[])
        with patch('clean_corpus.content_approved',content_approved):
            self.assertEqual(clean([self.row],[self.local,self.raw])[0],[])
            self.assertEqual(clean([self.row],[self.local,derived])[0],[self.row])
            other = dict(self.local,approved=False,transcript='你好皮克')
            self.assertEqual(clean([self.row],[self.local,derived,other])[0],[])
            with self.assertRaises(ValueError):clean([self.row],[self.local,derived],{'a'*64})


if __name__ == '__main__': unittest.main()
