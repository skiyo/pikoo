import unittest
import hashlib
from pathlib import Path
import tempfile
from generate_local_tts import jobs

class LocalCurriculumTest(unittest.TestCase):
    def test_v17_plan_is_disjoint_from_all_consumed_tests_and_new_development(self):
        from heldout_curriculum import jobs as heldout_jobs
        from generalization_curriculum import jobs as development_jobs
        from child_level_curriculum import jobs as child_jobs
        rows=heldout_jobs('v17')
        old=[r for version in ['v11','v12','v13','v14','v15','v16'] for r in heldout_jobs(version)]+development_jobs()+child_jobs()
        self.assertEqual(len(rows),256)
        for key in ['group','seed','instruction']:
            self.assertFalse({r[key] for r in rows}&{r[key] for r in old})
        self.assertTrue(all(r['split']=='test' and r['frozen_holdout'] and not r['family_inputs_used']
                            and not r['reference_audio_used'] and not r['real_child'] for r in rows))
        for style in ['adult','childlike']:
            selected=[r for r in rows if r['synthetic_style']==style]
            self.assertEqual(sum(r['label'] for r in selected),64)
            self.assertEqual(sum(not r['label'] for r in selected),64)
            self.assertEqual(sum(r['label'] and 'Pikoo' in r['text'] for r in selected),32)

    def test_content_screen_never_erases_unexpected_english_or_numbers(self):
        from review_local_corpus import content_approved
        from prepare_google_iteration import reviewed_content_matches
        for text,label in [('你好 Pikoo',1),('你好皮克',0)]:
            row={'source':'Qwen3-TTS-synthetic-local','label':label,'text':text}
            self.assertTrue(content_approved(row,text))
            for transcript in [text+' hello','hello '+text,text+' 123']:
                self.assertFalse(content_approved(row,transcript))
                self.assertFalse(reviewed_content_matches(row,transcript))

    def test_code_switch_training_has_literal_names_and_no_heldout_groups(self):
        from broad_curriculum import jobs as broad_jobs,code_switch_jobs
        rows=code_switch_jobs()
        self.assertEqual(len(rows),96)
        phonetic=code_switch_jobs('train','phonetic')
        self.assertTrue(all('Pee ' in r['text'] for r in phonetic if r['label']))
        self.assertFalse({r['seed'] for r in rows}&{r['seed'] for r in phonetic})
        english=code_switch_jobs('train','english')
        self.assertFalse({r['seed'] for r in rows+phonetic}&{r['seed'] for r in english})
        self.assertTrue(all(r['synthesis_language']=='English' and r['english_phonetic_surface'] and r['expected_spoken_transcript']=='你好皮酷' for r in english if r['label']))
        dev=code_switch_jobs('validation')
        self.assertEqual(len(dev),48)
        self.assertFalse({r['seed'] for r in rows}&{r['seed'] for r in dev})
        self.assertFalse({r['group'] for r in rows}&{r['group'] for r in dev})
        self.assertEqual({r['split'] for r in rows},{'train'})
        self.assertTrue(all('Pikoo' in r['text'] for r in rows if r['label']))
        self.assertFalse({r['seed'] for r in rows}&{r['seed'] for r in broad_jobs()})
        self.assertTrue(all(not r['family_inputs_used'] and not r['reference_audio_used'] for r in rows))
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
    def test_replacement_holdout_has_new_prompts_seeds_and_groups(self):
        from heldout_curriculum import jobs as heldout_jobs
        old=heldout_jobs('v11');new=heldout_jobs('v12')
        self.assertEqual(len(new),80)
        for key in ['group','seed','instruction']:
            self.assertFalse({r[key] for r in old}&{r[key] for r in new})
        self.assertTrue(all(r['split']=='test' and r['frozen_holdout'] for r in new))
        newest=heldout_jobs('v13')
        self.assertEqual(len(newest),96)
        for key in ['group','seed','instruction']:
            self.assertFalse({r[key] for r in old+new}&{r[key] for r in newest})
        self.assertTrue(any('Pee Koo' in r['text'] and r['synthesis_language']=='auto' for r in newest))
        next_=heldout_jobs('v14')
        self.assertEqual(len(next_),128)
        for key in ['group','seed','instruction']:
            self.assertFalse({r[key] for r in old+new+newest}&{r[key] for r in next_})
        for style in ['adult','childlike']:
            for pron in ['mandarin-pi2-ku4','mixed-pi1-ku1']:
                self.assertEqual(sum(r['label'] and r['synthetic_style']==style and r['pronunciation']==pron for r in next_),16)
        self.assertTrue(all(r['split']=='test' and r['frozen_holdout'] and not r['family_inputs_used'] for r in next_))
    def test_level_only_holdout_is_fresh_balanced_and_never_training(self):
        from heldout_curriculum import jobs as heldout_jobs
        rows=heldout_jobs('v15')
        old=[r for version in ['v11','v12','v13','v14'] for r in heldout_jobs(version)]
        self.assertEqual(len(rows),128)
        for key in ['group','seed','instruction']:
            self.assertFalse({r[key] for r in old}&{r[key] for r in rows})
        self.assertTrue(all(r['split']=='test' and r['frozen_holdout'] and not r['family_inputs_used']
                            and not r['reference_audio_used'] and not r['real_child'] for r in rows))
        self.assertEqual({r['pronunciation'] for r in rows if r['label']},{'mixed-pi1-ku1'})
        for style in ['adult','childlike']:
            selected=[r for r in rows if r['synthetic_style']==style]
            self.assertEqual(sum(r['label'] for r in selected),32)
            self.assertEqual(sum(not r['label'] for r in selected),32)
            self.assertEqual(sum(r['label'] and 'Pikoo' in r['text'] for r in selected),16)
        self.assertTrue(all(r['synthesis_language']=='auto' for r in rows if 'Pikoo' in r['text']))

    def test_v16_is_a_larger_disjoint_blind_plan_with_unchanged_target_meaning(self):
        from heldout_curriculum import jobs as heldout_jobs
        from level_tone_curriculum import jobs as training_jobs
        rows=heldout_jobs('v16')
        old=[r for version in ['v11','v12','v13','v14','v15'] for r in heldout_jobs(version)]+training_jobs()
        self.assertEqual(len(rows),256)
        self.assertEqual(len({r['group'] for r in rows}),32)
        self.assertEqual(len({r['seed'] for r in rows}),256)
        for key in ['group','seed','instruction']:
            self.assertFalse({r[key] for r in old}&{r[key] for r in rows})
        self.assertTrue(all(r['split']=='test' and r['frozen_holdout'] and not r['family_inputs_used']
                            and not r['reference_audio_used'] and not r['real_child'] for r in rows))
        self.assertEqual({r['pronunciation'] for r in rows if r['label']},{'mixed-pi1-ku1'})
        for style in ['adult','childlike']:
            selected=[r for r in rows if r['synthetic_style']==style]
            self.assertEqual(sum(r['label'] for r in selected),64)
            self.assertEqual(sum(not r['label'] for r in selected),64)
            self.assertEqual(sum(r['label'] and 'Pikoo' in r['text'] for r in selected),32)

    def test_pi_ke_negative_aliases_never_admit_pi_ku_or_extra_speech(self):
        from review_local_corpus import content_approved
        from prepare_google_iteration import reviewed_content_matches
        row={'source':'Google-Gemini-TTS-synthetic','label':0,'text':'你好皮克'}
        for transcript in ['你好，皮克。','你好，匹克。','你好，皮可。','你好披克']:
            self.assertTrue(content_approved(row,transcript))
            self.assertTrue(reviewed_content_matches(row,transcript))
        for transcript in ['你好皮酷','你好批枯','你好匹酷','你好皮','匹克','您好啊匹克','你好皮球','']:
            self.assertFalse(content_approved(row,transcript))
            self.assertFalse(reviewed_content_matches(row,transcript))
        self.assertFalse(content_approved({**row,'label':1},'你好皮可'))
        self.assertFalse(content_approved({**row,'text':'你好皮球'},'你好皮可'))

    def test_matched_prefix_review_rejects_full_names_and_unrelated_asr(self):
        from review_local_corpus import content_approved
        row={'source':'TTS-matched-incomplete-prefix','label':0}
        self.assertTrue(content_approved(row,'你好，皮。'))
        for text in ['你好皮酷','你好Pikoo','你好朋友','']:
            self.assertFalse(content_approved(row,text))
    def test_english_surface_requires_complete_greeting_and_both_name_syllables(self):
        from review_local_corpus import content_approved
        row={'label':1,'text':'Ni hao, pee coo.','english_phonetic_surface':True,'expected_spoken_transcript':'你好皮酷'}
        for transcript in ['Ni hao, pee coo.','Knee how, Pikoo!','你好皮酷','Ni hao, piku.']:
            self.assertTrue(content_approved(row,transcript),transcript)
        for transcript in ['你好皮','Ni hao, pee.','你好皮球','Ni hao, Pikoo, thank you.','unrelated English','']:
            self.assertFalse(content_approved(row,transcript),transcript)
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
