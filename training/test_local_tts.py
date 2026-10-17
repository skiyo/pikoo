import unittest
import hashlib
from pathlib import Path
import tempfile
from generate_local_tts import jobs

class LocalCurriculumTest(unittest.TestCase):
    def test_reference_and_renamed_household_audio_cannot_be_reviewed(self):
        from review_local_corpus import validate
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'renamed.wav';p.write_bytes(b'heldout fixture');digest=hashlib.sha256(p.read_bytes()).hexdigest()
            row=dict(source='Qwen3-TTS-synthetic-local',synthetic=True,path=p.name,sha256=digest)
            with self.assertRaisesRegex(ValueError,'Protected household'):validate([row],root,{digest})
            with self.assertRaisesRegex(ValueError,'without reference'):validate([{**row,'reference_audio_used':True}],root,set())
            with self.assertRaisesRegex(ValueError,'hash mismatch'):validate([{**row,'sha256':'invalid'}],root,set())
    def test_prompt_families_stay_in_one_split_and_cover_both_readings(self):
        rows=jobs();groups={}
        self.assertEqual(len(rows),96)
        for row in rows:
            self.assertEqual(groups.setdefault(row['group'],row['split']),row['split'])
            self.assertTrue(row['synthetic']);self.assertFalse(row['real_child']);self.assertFalse(row['reference_audio_used'])
        for profile in {r['profile'] for r in rows}:
            group=[r for r in rows if r['profile']==profile]
            self.assertEqual({r['label'] for r in group},{0,1})
            self.assertEqual({r['pronunciation'] for r in group if r['label']},{'mandarin-pi2-ku4','mixed-pi1-ku1'})

if __name__=='__main__':unittest.main()
