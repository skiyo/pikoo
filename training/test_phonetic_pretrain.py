import unittest
import tempfile,json,hashlib
from pathlib import Path
import numpy as np
from phonetic_pretrain import eligible,phones


class Tests(unittest.TestCase):
    def test_household_and_renamed_waveform_rejected(self):
        row={'source':'ChildMandarin','split':'train','sha256':'protected'}
        with self.assertRaisesRegex(ValueError,'Protected'):eligible(row,{'protected'})
        with self.assertRaisesRegex(ValueError,'Protected'):eligible({**row,'sha256':'other','evaluation_only':True},set())
    def test_official_validation_cannot_become_pretraining(self):
        self.assertFalse(eligible({'source':'ChildMandarin','split':'validation','sha256':'x'},set()))
    def test_binary_negative_prefix_cannot_inherit_full_phonetic_transcript(self):
        row={'source':'ChildMandarin','split':'train','sha256':'x'}
        self.assertTrue(eligible(row,set()))
        for key,value in [('mined_training_prefix',True),('parent_sha256','parent'),('causal_end_sample',16000),('augmentation',{'tempo':1.1})]:
            self.assertFalse(eligible({**row,key:value},set()))
    def test_frozen_synthetic_cannot_become_pretraining(self):
        with self.assertRaisesRegex(ValueError,'Protected'):
            eligible({'source':'Qwen3-TTS-synthetic-local','split':'train','sha256':'x','frozen_holdout':True},set())
    def test_complete_name_and_competitors_have_distinct_phone_sequences(self):
        self.assertEqual(phones('你好Pikoo'),phones('你好皮酷'))
        self.assertNotEqual(phones('你好皮酷'),phones('你好酷酷'))
        self.assertNotEqual(phones('你好皮酷'),phones('你好皮球'))
        self.assertNotEqual(phones('你好皮酷'),phones('你好皮'))
    def test_explicit_larger_width_keeps_legacy_defaults(self):
        from phonetic_pretrain import flags
        self.assertEqual(flags([3,5,7]).pointwise_filters,'128,128,128')
        bigger=flags([3,5,7,9],192,96)
        self.assertEqual(bigger.pointwise_filters,'192,192,192,192')
        self.assertEqual(bigger.first_conv_filters,96)
        with self.assertRaises(ValueError):flags([3,5],512,64)
    def test_raw_feature_reuse_proves_labels_and_folds_before_context_change(self):
        from phonetic_pretrain import reuse_feature_cache
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'old';source.mkdir();protection=root/'protection.json';protection.write_text('{"audio_sha256":{}}')
            spec={'manifest_sha256':'same-manifest','left_context':60,'protected_sha256':'new-protection','rows':['same-corpus-identity']}
            old={**spec,'left_context':36,'protected_sha256':hashlib.sha256(protection.read_bytes()).hexdigest()}
            (source/'features.sha256').write_text(hashlib.sha256(json.dumps(old,sort_keys=True).encode()).hexdigest())
            (source/'report.json').write_text(json.dumps({'manifest_sha256':'same-manifest','left_context_frames':36,'household_used':False,'official_validation_or_test_used':False}))
            y=np.zeros((2,74),np.int32);y[:,0]=1;y[:,1]=60;y[:,2]=[1,2]
            np.savez(source/'features.npz',x=np.zeros((2,399,40),np.float32),y=y,folds=np.array([False,True]))
            rows=[{'tokens':['one'],'fold':'train'},{'tokens':['two'],'fold':'validation'}];ids={'one':1,'two':2}
            x,labels,folds,proof=reuse_feature_cache(source,protection,spec,rows,ids,root/'new.npz')
            self.assertEqual(x.dtype,np.float32);self.assertTrue(proof['current_waveforms_rechecked'])
            self.assertEqual((root/'new.npz').read_bytes(),(source/'features.npz').read_bytes())
            with self.assertRaisesRegex(ValueError,'identity'):
                reuse_feature_cache(source,protection,{**spec,'rows':['different']},rows,ids,root/'bad.npz')
            with self.assertRaisesRegex(ValueError,'labels or held-out folds'):
                reuse_feature_cache(source,protection,spec,[{**rows[0],'fold':'validation'},rows[1]],ids,root/'bad-fold.npz')


if __name__=='__main__':unittest.main()
