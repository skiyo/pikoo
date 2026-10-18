import unittest
from phonetic_pretrain import eligible,phones


class Tests(unittest.TestCase):
    def test_household_and_renamed_waveform_rejected(self):
        row={'source':'ChildMandarin','split':'train','sha256':'protected'}
        with self.assertRaisesRegex(ValueError,'Protected'):eligible(row,{'protected'})
        with self.assertRaisesRegex(ValueError,'Protected'):eligible({**row,'sha256':'other','evaluation_only':True},set())
    def test_official_validation_cannot_become_pretraining(self):
        self.assertFalse(eligible({'source':'ChildMandarin','split':'validation','sha256':'x'},set()))
    def test_frozen_synthetic_cannot_become_pretraining(self):
        with self.assertRaisesRegex(ValueError,'Protected'):
            eligible({'source':'Qwen3-TTS-synthetic-local','split':'train','sha256':'x','frozen_holdout':True},set())
    def test_complete_name_and_competitors_have_distinct_phone_sequences(self):
        self.assertEqual(phones('你好Pikoo'),phones('你好皮酷'))
        self.assertNotEqual(phones('你好皮酷'),phones('你好酷酷'))
        self.assertNotEqual(phones('你好皮酷'),phones('你好皮球'))
        self.assertNotEqual(phones('你好皮酷'),phones('你好皮'))


if __name__=='__main__':unittest.main()
