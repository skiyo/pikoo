import unittest
from child_level_curriculum import jobs
from heldout_curriculum import jobs as heldout_jobs


class ChildLevelCurriculumTest(unittest.TestCase):
    def test_child_focused_conditions_preserve_train_only_split_and_complete_names(self):
        rows=jobs();self.assertEqual(len(rows),320)
        self.assertEqual(len({r['group'] for r in rows}),40)
        self.assertEqual({r['split'] for r in rows},{'train'})
        self.assertTrue(all(not r['real_child'] and not r['reference_audio_used'] and not r['family_inputs_used']
                            and not r.get('frozen_holdout') and r['synthesis_language']=='Chinese' for r in rows))
        self.assertEqual({r['pronunciation'] for r in rows if r['label']},{'mixed-pi1-ku1'})
        self.assertEqual(sum(r['label'] and r['synthetic_style']=='childlike' for r in rows),128)
        self.assertEqual(sum(r['label'] and r['synthetic_style']=='adult' for r in rows),32)
        self.assertEqual(sum(not r['label'] for r in rows),160)
        self.assertFalse(any(r['text']=='你好皮酷' for r in rows))
        old=[r for version in ['v11','v12','v13','v14','v15','v16'] for r in heldout_jobs(version)]
        for key in ['group','seed','instruction']:
            self.assertFalse({r[key] for r in rows}&{r[key] for r in old})


if __name__=='__main__':unittest.main()
