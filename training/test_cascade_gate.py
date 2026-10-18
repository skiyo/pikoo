import unittest
from cascade_gate import combine


class Tests(unittest.TestCase):
    def fixture(self):
        p={'threshold':.9,'models':{'candidate':'model'},'details':[{'sha256':'x','label':0,'source':'synthetic','seconds':1,'scores':{'candidate':.95},'detected':{'candidate':True}}]}
        prepared=[{'id':0,'sha256':'x','label':0,'stage1_trigger_sample':20000}]
        result=[{'id':0,'sha256':'x','label':0,'samples':86400,'top_id':2,'top_probability':.8}]
        policy={'primary_threshold':.9,'primary_model_sha256':'model','pre_roll_samples':64000,'lookahead_samples':9600,'trailing_silence_samples':12800,'veto_command_ids':[2],'veto_probability':.5,'rearm_guard_ms':5000}
        return p,prepared,result,policy
    def test_veto_does_not_mutate_original(self):
        args=self.fixture();out=combine(*args)
        self.assertFalse(out['details'][0]['detected']['candidate'])
        self.assertTrue(args[0]['details'][0]['detected']['candidate'])
    def test_unknown_keeps_primary(self):
        p,prepared,result,policy=self.fixture();result[0]['top_id']=0;result[0]['top_probability']=0
        self.assertTrue(combine(p,prepared,result,policy)['details'][0]['detected']['candidate'])
    def test_invalid_scores_rejected(self):
        p,prepared,result,policy=self.fixture();result[0]['top_probability']=float('nan')
        with self.assertRaisesRegex(ValueError,'Invalid verifier'):combine(p,prepared,result,policy)
    def test_changed_primary_decision_rejected(self):
        p,prepared,result,policy=self.fixture();p['details'][0]['scores']['candidate']=.8
        with self.assertRaisesRegex(ValueError,'Inconsistent primary'):combine(p,prepared,result,policy)
    def test_rearm_tail_requires_full_replay(self):
        p,prepared,result,policy=self.fixture();p['details'][0]['seconds']=12
        with self.assertRaisesRegex(ValueError,'rearm'):combine(p,prepared,result,policy)
    def test_missing_replay_rejected(self):
        p,prepared,_,policy=self.fixture()
        with self.assertRaisesRegex(ValueError,'complete replay'):combine(p,prepared,[],policy)
    def test_protected_audio_rejected(self):
        p,prepared,result,policy=self.fixture();p['details'][0]['evaluation_only']=True
        with self.assertRaisesRegex(ValueError,'Protected'):combine(p,prepared,result,policy)


if __name__=='__main__':unittest.main()
