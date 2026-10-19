import unittest
from level_tone_curriculum import jobs
from heldout_curriculum import jobs as test_jobs


class LevelToneCurriculumTest(unittest.TestCase):
    def test_balanced_phrases_and_disjoint_train_only_groups(self):
        rows=jobs();old=[r for version in ['v11','v12','v13','v14','v15'] for r in test_jobs(version)]
        self.assertEqual(len(rows),96)
        self.assertEqual({r['split'] for r in rows},{'train'})
        self.assertEqual({r['pronunciation'] for r in rows if r['label']},{'mixed-pi1-ku1'})
        self.assertEqual(sum(r['label'] and r['synthetic_style']=='adult' for r in rows),32)
        self.assertEqual(sum(r['label'] and r['synthetic_style']=='childlike' for r in rows),16)
        self.assertEqual(sum(not r['label'] for r in rows),48)
        self.assertTrue(all(not r['family_inputs_used'] and not r['reference_audio_used'] and not r['real_child'] for r in rows))
        for key in ['group','seed','instruction']:
            self.assertFalse({r[key] for r in rows}&{r[key] for r in old})
        self.assertFalse(any(r['text']=='你好皮酷' for r in rows))


if __name__=='__main__':unittest.main()
