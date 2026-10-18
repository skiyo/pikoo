import copy
import unittest
from streaming_gate import assess


class StreamingGateTest(unittest.TestCase):
    def fixture(self):
        policy={'threshold':.9,'rolling_inferences':5,'old_original_targets':46,'old_original_target_min_hits':44,
          'firmware_max_bytes':524288,'validation_non_target_false_wakes_max':0,'primary_new_targets_min_recall':.9,
          'each_new_pronunciation_and_style_min_recall':.9,'new_pitch_tempo_min_recall':.9}
        rows=[]
        def row(source,label,detected,**kw):
            r={'source':source,'label':label,'detected':{'candidate':detected},'condition':'clean','sha256':str(len(rows)),**kw};rows.append(r)
        for _ in range(46):row('known-self-test-v1-validation',1,True)
        legacy={r['sha256'] for r in rows}
        for style in ['adult','childlike']:
            for pronunciation in ['mandarin-pi2-ku4','mixed-pi1-ku1']:
                for _ in range(10):row('Qwen3-TTS-synthetic-local',1,True,speaker='qwen-broad:fixture',synthetic_style=style,pronunciation=pronunciation)
        for _ in range(10):row('pitch-tempo-augmented-Qwen3-TTS',1,True)
        row('ChildMandarin',0,False,real_child=True)
        row('Qwen3-TTS-synthetic-local',0,False,speaker='qwen-broad:fixture')
        return {'threshold':.9,'details':rows},policy,legacy

    def test_larger_budget_never_relaxes_false_wake_or_pronunciation_checks(self):
        ev,policy,legacy=self.fixture()
        self.assertTrue(assess(ev,policy,legacy,200000)['passed'])
        ev['details'][-1]['detected']['candidate']=True
        self.assertIn('false-wakes',assess(ev,policy,legacy,200000)['failures'])
        ev,policy,legacy=self.fixture()
        for r in ev['details'][56:58]:r['detected']['candidate']=False
        self.assertIn('adult:mixed-pi1-ku1',assess(ev,policy,legacy,200000)['failures'])
        self.assertIn('model-size',assess(ev,policy,legacy,600000)['failures'])

    def test_removed_legacy_target_or_household_input_cannot_select_model(self):
        ev,policy,legacy=self.fixture()
        removed=copy.deepcopy(ev);removed['details'].pop(0)
        with self.assertRaisesRegex(ValueError,'missing or duplicated'):assess(removed,policy,legacy,200000)
        for field,value in [('evaluation_only',True),('frozen_holdout',True),('source','private-household')]:
            contaminated=copy.deepcopy(ev);contaminated['details'][0][field]=value
            with self.assertRaisesRegex(ValueError,'cannot select'):assess(contaminated,policy,legacy,200000)

    def test_diagnostic_context_cannot_silently_replace_the_fixed_gate(self):
        ev,policy,legacy=self.fixture()
        ev['input_context']={'lead_seconds':4.5,'background_rms':20.}
        with self.assertRaisesRegex(ValueError,'input context'):assess(ev,policy,legacy,200000)
        policy['input_context']=dict(ev['input_context'])
        self.assertTrue(assess(ev,policy,legacy,200000)['passed'])


if __name__=='__main__':unittest.main()
