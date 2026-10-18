import copy
import json
from pathlib import Path
import unittest
from level_tone_scope import focused,assess


class LevelToneScopeTest(unittest.TestCase):
    def fixture(self):
        rows=[]
        for style in ['adult','childlike']:
            for source in ['synthetic','pitch-tempo-augmented-synthetic']:
                rows.append({'sha256':str(len(rows)),'source':source,'label':1,'synthetic_style':style,
                             'pronunciation':'mixed-pi1-ku1','detected':{'candidate':True},'condition':'clean'})
        rows.append({'sha256':'negative','source':'ChildMandarin','label':0,'detected':{'candidate':False},'condition':'clean'})
        policy=json.loads((Path(__file__).parent/'policies/dualeye-pikoo-level-v1.json').read_text())
        return rows,policy,{'threshold':.9,'input_context':policy['input_context'],'details':copy.deepcopy(rows)}

    def test_unspecified_positive_is_removed_and_never_flipped_to_negative(self):
        rows,_,_=self.fixture();old={'sha256':'old','source':'synthetic','label':1,'pronunciation':'mandarin-pi2-ku4'}
        self.assertEqual(focused(rows+[old]),rows)
        self.assertEqual(old['label'],1)
        self.assertEqual(len([r for r in focused(rows+[old]) if not r['label']]),1)

    def test_dropped_negative_and_bad_adult_child_or_augmented_recall_fail(self):
        rows,policy,ev=self.fixture();self.assertTrue(assess(ev,policy,rows,190000)['passed'])
        removed=copy.deepcopy(ev);removed['details'].pop()
        with self.assertRaisesRegex(ValueError,'mandatory negatives'):assess(removed,policy,rows,190000)
        ev['details'][-1]['detected']['candidate']=True
        self.assertIn('false-wakes',assess(ev,policy,rows,190000)['failures'])
        for index,reason in [(0,'adult-raw-level-targets'),(2,'childlike-raw-level-targets'),(1,'pitch-tempo-level-targets')]:
            modified=copy.deepcopy(ev);modified['details'][index]['detected']['candidate']=False
            self.assertIn(reason,assess(modified,policy,rows,190000)['failures'])

    def test_protected_identity_and_context_cannot_be_reused(self):
        rows,policy,ev=self.fixture()
        with self.assertRaisesRegex(ValueError,'Protected'):focused(rows,{'0'})
        ev['input_context']={'lead_seconds':5.,'background_rms':0.}
        with self.assertRaisesRegex(ValueError,'context'):assess(ev,policy,rows,190000)


if __name__=='__main__':unittest.main()
