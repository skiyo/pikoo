import copy,unittest
from generalization_gate import assess


class GeneralizationGateTest(unittest.TestCase):
    def fixture(self):
        expected=[]
        for style in ['adult','childlike']:
            for index in range(24):
                label=int(index<12)
                expected.append(dict(sha256=f'{style}:{index}',label=label,split='validation',
                    pronunciation='mixed-pi1-ku1' if label else 'non-target',synthetic_style=style,
                    source='Qwen3-TTS-synthetic-local',synthetic=True,group='qwen-generalization-development-v1:fixture',
                    preassigned_usage='validation',text='你好 Pikoo' if index<4 else '你好批枯' if label else '你好皮克'))
        rows=[dict(r,detected={'candidate':bool(r['label'])}) for r in expected]
        return expected,dict(details=rows,threshold=.9,rolling_inferences=5,input_context={'lead_seconds':1.,'background_rms':0.})

    def test_new_development_never_overrides_original_failure_or_false_wakes(self):
        expected,evaluation=self.fixture()
        self.assertTrue(assess(evaluation,expected,{'passed':True})['passed'])
        self.assertFalse(assess(evaluation,expected,{'passed':False})['passed'])
        evaluation['details'][-1]['detected']['candidate']=True
        self.assertIn('additional-false-wakes',assess(evaluation,expected,{'passed':True})['failures'])

    def test_literal_name_and_style_gates_cannot_be_hidden_in_aggregate(self):
        expected,evaluation=self.fixture()
        evaluation['details'][0]['detected']['candidate']=False
        self.assertIn('adult:English-recall',assess(evaluation,expected,{'passed':True})['failures'])

    def test_protected_or_missing_cases_fail_closed(self):
        expected,evaluation=self.fixture()
        with self.assertRaisesRegex(ValueError,'Protected'):assess(evaluation,expected,{'passed':True},[expected[0]['sha256']])
        evaluation['details'].pop()
        with self.assertRaisesRegex(ValueError,'Missing'):assess(evaluation,expected,{'passed':True})
        bad=copy.deepcopy(expected);bad[0]['preassigned_usage']='train'
        with self.assertRaisesRegex(ValueError,'preassigned'):assess(evaluation,bad,{'passed':True})
        bad=copy.deepcopy(expected);bad[0]['pronunciation']='mandarin-pi2-ku4'
        with self.assertRaisesRegex(ValueError,'pronunciation'):assess(evaluation,bad,{'passed':True})


if __name__=='__main__':unittest.main()
