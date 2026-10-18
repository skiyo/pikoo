import unittest
import hashlib
from pathlib import Path
import tempfile
from generate_local_tts import jobs

class LocalCurriculumTest(unittest.TestCase):
    def test_hard_contrasts_preserve_training_groups_and_fresh_seeds(self):
        from broad_curriculum import jobs as broad_jobs,hard_contrast_jobs
        original=broad_jobs();rows=hard_contrast_jobs()
        self.assertEqual(len(rows),96)
        self.assertEqual({r['split'] for r in rows},{'train'})
        self.assertFalse({r['group'] for r in rows}&{r['group'] for r in original if r['split']!='train'})
        self.assertFalse({r['seed'] for r in rows}&{r['seed'] for r in original})
        self.assertTrue({'你好皮球','你好酷酷','你真酷'}<={r['text'] for r in rows if not r['label']})
    def test_fresh_synthetic_holdout_is_never_a_development_voice_group(self):
        from heldout_curriculum import jobs as heldout_jobs
        from broad_curriculum import jobs as broad_jobs
        rows=heldout_jobs()
        self.assertEqual(len(rows),80)
        self.assertEqual({r['split'] for r in rows},{'test'})
        self.assertTrue(all(r['frozen_holdout'] and not r['family_inputs_used'] and not r['reference_audio_used'] for r in rows))
        self.assertFalse({r['group'] for r in rows}&{r['group'] for r in jobs()+broad_jobs()})
        for style in ['adult','childlike']:
            self.assertEqual({r['pronunciation'] for r in rows if r['synthetic_style']==style and r['label']},{'mandarin-pi2-ku4','mixed-pi1-ku1'})
    def test_matched_prefix_review_rejects_full_names_and_unrelated_asr(self):
        from review_local_corpus import content_approved
        row={'source':'TTS-matched-incomplete-prefix','label':0}
        self.assertTrue(content_approved(row,'你好，皮。'))
        for text in ['你好皮酷','你好Pikoo','你好朋友','']:
            self.assertFalse(content_approved(row,text))
    def test_broad_curriculum_assigns_conditions_before_generation(self):
        from broad_curriculum import jobs as broad_jobs
        rows=broad_jobs();groups={}
        for row in rows:
            self.assertEqual(groups.setdefault(row['group'],row['split']),row['split'])
            self.assertFalse(row['real_child'] or row['reference_audio_used'] or row['family_inputs_used'])
        self.assertEqual(sum(s=='train' for s in groups.values()),24)
        self.assertEqual(sum(s=='validation' for s in groups.values()),12)
        for split in ('train','validation'):
            for style in ('adult','childlike'):
                self.assertEqual({r['label'] for r in rows if r['split']==split and r['synthetic_style']==style},{0,1})
    def test_extra_contrasts_never_regenerate_development_prompt_families(self):
        rows=jobs(contrasts=True)
        self.assertEqual({r['split'] for r in rows},{'train'})
        self.assertFalse({r['group'] for r in rows}&{r['group'] for r in jobs() if r['split']!='train'})
        self.assertTrue(any(r['text']=='你好皮' and not r['label'] for r in rows))
        self.assertTrue(any(r['pronunciation']=='mixed-pi1-ku1' and r['label'] for r in rows))
    def test_child_phonetic_curriculum_remains_training_only(self):
        rows=jobs(child_focus=True,phonetic_spelling=True)
        self.assertEqual({r['split'] for r in rows},{'train'})
        self.assertEqual({r['synthetic_style'] for r in rows},{'childlike'})
        self.assertFalse(any(r['real_child'] or r['reference_audio_used'] for r in rows))
        self.assertFalse(any('Pikoo' in r['text'] for r in rows))
        self.assertEqual({r['pronunciation'] for r in rows if r['label']},{'mandarin-pi2-ku4','mixed-pi1-ku1'})
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
