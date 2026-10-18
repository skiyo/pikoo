import importlib.util
import tempfile
import unittest
import wave
from pathlib import Path

AVAILABLE=all(importlib.util.find_spec(name) for name in ('tensorflow','numpy','pymicro_features'))


@unittest.skipUnless(AVAILABLE,'Optional training runtime is not installed')
class AlignmentTest(unittest.TestCase):
    def test_positive_completion_tail_preserves_whole_phrase_and_idle_lead(self):
        import numpy as np
        from unittest.mock import patch
        from train import dataset
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);captured=[]
            def fixture(samples):
                with wave.open(str(root/'target.wav'),'wb') as w:
                    w.setparams((1,2,16000,0,'NONE','not compressed'))
                    w.writeframes(np.full(samples,10000,dtype='<i2').tobytes())
            row=dict(path='target.wav',label=1,split='train',group='fixture')
            fixture(58000)
            def capture(pcm):
                captured.append(pcm.copy());return np.zeros((399,40),np.float32)
            class QuietRNG:
                def __init__(self):self.rng=np.random.default_rng(42)
                def __getattr__(self,name):return getattr(self.rng,name)
                def normal(self,mean,scale,size):return np.zeros(size)
            quiet=QuietRNG()
            with patch('train.features',side_effect=capture),patch('train.np.random.default_rng',return_value=quiet):
                dataset([row],root,window_frames=399,positive_repeats=1,pcm_context=True,positive_tail_seconds=.6)
            pcm=captured[0];active=np.flatnonzero(np.abs(pcm.astype(float))>1000)
            self.assertLessEqual(len(pcm),(399+2)*160)
            self.assertGreaterEqual(active[0],4800)
            factor=np.random.default_rng(42).uniform(.88,1.12)
            self.assertEqual(len(active),len(np.arange(0,58000,factor)))
            fixture(80000)
            with self.assertRaisesRegex(ValueError,'Complete TRAIN target cannot fit'):
                dataset([row],root,window_frames=399,positive_repeats=1,pcm_context=True,positive_tail_seconds=.6)
            for value in [0,1,float('nan')]:
                with self.assertRaisesRegex(ValueError,'Positive tail'):
                    dataset([],root,positive_tail_seconds=value)

    def test_late_negative_context_does_not_move_positives_or_evaluation(self):
        import numpy as np
        from train import dataset
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with wave.open(str(root/'short.wav'),'wb') as w:
                w.setparams((1,2,16000,0,'NONE','not compressed'))
                w.writeframes((np.sin(np.arange(8000)*.15)*4000).astype('<i2').tobytes())
            for split,label in [('train',1),('validation',0),('test',0),('train',0)]:
                row=dict(path='short.wav',label=label,split=split,group='fixture')
                default=dataset([row],root,window_frames=399,pcm_context=True,positive_repeats=2,negative_repeats=2)
                late=dataset([row],root,window_frames=399,pcm_context=True,positive_repeats=2,negative_repeats=2,negative_tail_seconds=1.2)
                if split=='train' and label==0:
                    self.assertFalse(np.array_equal(default[split][0][0],late[split][0][0]))
                else:np.testing.assert_array_equal(default[split][0],late[split][0])
                if split!='train' or not label:
                    completion=dataset([row],root,window_frames=399,pcm_context=True,positive_repeats=2,negative_repeats=2,positive_tail_seconds=.6)
                    np.testing.assert_array_equal(default[split][0],completion[split][0])
            for value in [0,2,float('nan')]:
                with self.assertRaisesRegex(ValueError,'Negative tail'):
                    dataset([],root,negative_tail_seconds=value)

    def test_external_evaluation_recordings_never_enter_training_pipeline(self):
        from train import dataset, validate_training_manifest
        for split in ('train','validation','test'):
            for flag in ['evaluation_only','frozen_holdout']:
                row=dict(path='must-not-read.wav',label=1,split=split,group='heldout',**{flag:True})
                with self.subTest(split=split,flag=flag):
                    with self.assertRaisesRegex(ValueError,'separate evaluation manifest'):
                        validate_training_manifest([row])
                    with self.assertRaisesRegex(ValueError,'separate evaluation manifest'):
                        dataset([row],Path('/nonexistent'))

    def test_pcm_context_uses_real_features_for_idle_prefix(self):
        import numpy as np
        from train import dataset
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);signal=(np.sin(np.arange(8000)*.15)*4000).astype('<i2')
            with wave.open(str(root/'short.wav'),'wb') as w:
                w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(signal.tobytes())
            row=dict(path='short.wav',label=1,split='validation',group='fixture')
            before=dataset([row],root,window_frames=399)['validation'][0][0]
            after=dataset([row],root,window_frames=399,pcm_context=True)['validation'][0][0]
            self.assertEqual(after.shape,(399,40))
            self.assertTrue(np.all(before[:100]==0))
            self.assertGreater(float(np.mean(after[:100])),0)

    def test_quantization_matches_device_half_away_rounding(self):
        import numpy as np
        from streaming_runtime import quantize
        np.testing.assert_array_equal(quantize([.5,1.5,-.5,-1.5],1,0),[1,2,-1,-2])
        np.testing.assert_array_equal(quantize([1.5],1,-7),[-5])
        np.testing.assert_array_equal(quantize([1000,-1000],1,0),[127,-128])

    def test_following_sentence_does_not_change_positive_window(self):
        import numpy as np
        from train import dataset
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);prefix=(np.sin(np.arange(16000)*.15)*4000).astype('<i2')
            for name,suffix in [('a',np.zeros(24000,dtype='<i2')),('b',np.ones(24000,dtype='<i2')*12000)]:
                with wave.open(str(root/(name+'.wav')),'wb') as w:
                    w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(np.concatenate([prefix,suffix]).tobytes())
            def row(name,end):return dict(path=name+'.wav',label=1,split='validation',group='fixture',wake_end_sample=end)
            first=dataset([row('a',16000)],root,window_frames=399)['validation'][0][0]
            second=dataset([row('b',16000)],root,window_frames=399)['validation'][0][0]
            np.testing.assert_array_equal(first,second)
            with self.assertRaisesRegex(ValueError,'Invalid labeled wake end'):
                dataset([row('a',50000)],root,window_frames=399)


if __name__=='__main__':unittest.main()
