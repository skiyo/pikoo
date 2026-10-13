import importlib.util
import tempfile
import unittest
import wave
from pathlib import Path

AVAILABLE=all(importlib.util.find_spec(name) for name in ('tensorflow','numpy','pymicro_features'))


@unittest.skipUnless(AVAILABLE,'Optional training runtime is not installed')
class AlignmentTest(unittest.TestCase):
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
