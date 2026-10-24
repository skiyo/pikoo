import hashlib
import importlib.util
import tempfile
import unittest
import wave
from pathlib import Path
AVAILABLE=all(importlib.util.find_spec(name) for name in ('numpy','tensorflow','pymicro_features'))
if AVAILABLE:
    import numpy as np
    from speech_context import SpeechContext


@unittest.skipUnless(AVAILABLE,'Optional training runtime is not installed')
class SpeechContextTests(unittest.TestCase):
    def test_target_and_tail_are_preserved_and_validation_never_supplies_speech(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            path=root/'speech.wav'
            with wave.open(str(path),'wb') as stream:
                stream.setparams((1,2,16000,0,'NONE','not compressed'))
                stream.writeframes((np.sin(np.arange(16000*9)*.1)*3000).astype('<i2').tobytes())
            train=dict(path='speech.wav',split='train',label=0,source='ChildMandarin',sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            # This missing validation path must never be read as a prefix.
            val=dict(train,split='validation',path='must-not-read.wav')
            context=SpeechContext([train,val],root)
            self.assertEqual(context.pool,[train])
            original=np.concatenate([np.zeros(4800),np.arange(20000,dtype=np.float32)])
            result=context.apply(original,4800)
            np.testing.assert_array_equal(result[-20000:],original[4800:])
            self.assertGreater(len(result),len(original))

    def test_validation_features_and_baseline_randomness_are_unchanged(self):
        from train import dataset
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'speech.wav'
            with wave.open(str(path),'wb') as stream:
                stream.setparams((1,2,16000,0,'NONE','not compressed'))
                stream.writeframes(np.full(16000*9,3000,dtype='<i2').tobytes())
            train=dict(path='speech.wav',split='train',label=0,source='ChildMandarin',group='train',sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            # Separate waveforms/groups for targets in each split.
            rows=[train]
            for split in ['train','validation','test']:
                name=split+'.wav'
                with wave.open(str(root/name),'wb') as stream:
                    stream.setparams((1,2,16000,0,'NONE','not compressed'))
                    stream.writeframes(np.full(4000,1000+len(split),dtype='<i2').tobytes())
                rows.append(dict(path=name,split=split,label=1,group=split+'-target'))
            def features(pcm):
                return np.full((198,40),float(np.mean(pcm)),np.float32)
            with patch('train.features',side_effect=features):
                baseline=dataset(rows,root,positive_repeats=1)
                context=dataset(rows,root,positive_repeats=1,speech_context_probability=1.)
                balanced=dataset(rows,root,positive_repeats=1,speech_context_probability=1.,speech_context_negatives=True)
            for split in ['validation','test']:
                np.testing.assert_array_equal(baseline[split][0],context[split][0])
                np.testing.assert_array_equal(baseline[split][0],balanced[split][0])
            np.testing.assert_array_equal(baseline['train'][0][0],context['train'][0][0])
            self.assertFalse(np.array_equal(baseline['train'][0][0],balanced['train'][0][0]))
            target_index=int(np.flatnonzero(baseline['train'][1]==1)[0])
            self.assertFalse(np.array_equal(baseline['train'][0][target_index],context['train'][0][target_index]))

    def test_protected_input_and_nontrain_pool_are_rejected(self):
        base=dict(split='train',label=0,source='ChildMandarin')
        for flag in ['evaluation_only','frozen_holdout']:
            with self.assertRaises(ValueError):SpeechContext([dict(base,**{flag:True})],'.')
        with self.assertRaises(ValueError):SpeechContext([dict(base,split='validation')],'.')


if __name__=='__main__':unittest.main()
