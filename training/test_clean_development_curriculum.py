import unittest
import subprocess
import sys
from pathlib import Path
from clean_development_curriculum import jobs
from generalization_curriculum import jobs as generalization_jobs
from child_level_curriculum import jobs as child_jobs
from broad_curriculum import jobs as broad_jobs, code_switch_jobs
from heldout_curriculum import jobs as heldout_jobs


class CleanDevelopmentCurriculumTest(unittest.TestCase):
    def test_content_plan_is_balanced_and_fixed_before_synthesis(self):
        rows = jobs()
        self.assertEqual(rows, jobs())
        self.assertEqual(len(rows), 160)
        self.assertEqual(len({r['seed'] for r in rows}), 160)
        for style in ['adult', 'childlike']:
            group = [r for r in rows if r['synthetic_style'] == style]
            self.assertEqual(sum(r['label'] for r in group), 48)
            self.assertEqual(sum(not r['label'] for r in group), 32)
            self.assertEqual(sum(r['label'] and 'Pikoo' in r['text'] for r in group), 32)
            self.assertEqual(len({r['group'] for r in group}), 8)
        self.assertTrue(all(r['split'] == r['preassigned_usage'] == 'validation'
            and r['synthetic'] and not r['real_child'] and not r['reference_audio_used']
            and not r['family_inputs_used'] and not r.get('evaluation_only')
            and not r.get('frozen_holdout') for r in rows))

    def test_no_prior_training_development_or_sealed_conditions_are_reused(self):
        old = generalization_jobs() + child_jobs() + broad_jobs()
        old += [r for version in ['v11','v12','v13','v14','v15','v16','v17']
                for r in heldout_jobs(version)]
        old += [r for split in ['train','validation'] for spelling in ['brand','phonetic','english']
                for r in code_switch_jobs(split, spelling)]
        for key in ['seed', 'group', 'instruction']:
            self.assertFalse({r[key] for r in jobs()} & {r[key] for r in old})

    def test_generator_rejects_mixing_supplement_with_sealed_or_training_jobs(self):
        script=Path(__file__).with_name('generate_local_tts.py')
        for flag in ['--heldout','--contrasts','--child-level-contrasts','--generalization-contrasts']:
            process=subprocess.run([sys.executable,str(script),'--model','unused-model',
                '--output','unused-output','--clean-development',flag],capture_output=True,text=True)
            self.assertNotEqual(process.returncode,0)
            self.assertIn('Choose content-clean DEVELOPMENT independently',process.stderr)
