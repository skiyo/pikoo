import unittest
from generalization_curriculum import jobs
from heldout_curriculum import jobs as heldout_jobs
from child_level_curriculum import jobs as child_jobs


class GeneralizationCurriculumTest(unittest.TestCase):
    def test_preassigned_splits_and_styles_never_reuse_sealed_conditions(self):
        rows=jobs();self.assertEqual(len(rows),256)
        for split in ['train','validation']:
            selected=[r for r in rows if r['split']==split]
            self.assertEqual(len(selected),128)
            for style in ['adult','childlike']:
                group=[r for r in selected if r['synthetic_style']==style]
                self.assertEqual(sum(r['label'] for r in group),32)
                self.assertEqual(sum(not r['label'] for r in group),32)
                self.assertEqual(sum(r['label'] and 'Pikoo' in r['text'] for r in group),16)
        train=[r for r in rows if r['split']=='train'];dev=[r for r in rows if r['split']=='validation']
        old=child_jobs()+[r for version in ['v11','v12','v13','v14','v15','v16'] for r in heldout_jobs(version)]
        for key in ['group','seed','instruction']:
            self.assertFalse({r[key] for r in train}&{r[key] for r in dev})
            self.assertFalse({r[key] for r in rows}&{r[key] for r in old})
        self.assertTrue(all(not r.get('frozen_holdout') and not r.get('evaluation_only') and not r['real_child']
                            and not r['reference_audio_used'] and not r['family_inputs_used']
                            and r['preassigned_usage']==r['split'] for r in rows))


if __name__=='__main__':unittest.main()
