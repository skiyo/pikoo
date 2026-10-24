"""TRAIN curriculum changes must not perturb an explicitly stable DEV split."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import wave


@unittest.skipUnless(importlib.util.find_spec('tensorflow') and importlib.util.find_spec('pymicro_features'), 'Optional training runtime')
class SplitRandomnessTest(unittest.TestCase):
    def fixture(self, root):
        import numpy as np
        import hashlib
        rows=[]
        for index,split in enumerate(['train','validation','train','validation']):
            path=root/f'{index}.wav'
            pcm=(2000*np.sin(2*np.pi*(180+index*40)*np.arange(12800)/16000)).astype('<i2')
            with wave.open(str(path),'wb') as audio:
                audio.setparams((1,2,16000,0,'NONE','not compressed'));audio.writeframes(pcm.tobytes())
            rows.append(dict(path=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                split=split,label=int(index<2),speaker=f'fictional-{index}',group=f'fictional-{index}'))
        return rows

    def test_more_train_repetitions_leave_all_development_features_and_noise_fixed(self):
        import numpy as np
        from train import dataset
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rows=self.fixture(root)
            options=dict(window_frames=150,negative_repeats=1,pcm_context=True,stable_split_rng=True)
            before=dataset(rows,root,positive_repeats=1,**options)
            after=dataset(rows,root,positive_repeats=4,**options)
            self.assertNotEqual(len(before['train'][1]),len(after['train'][1]))
            for split in ['validation','test']:
                for a,b in zip(before[split],after[split]):np.testing.assert_array_equal(a,b)

    def test_legacy_mode_remains_explicit_and_reproduces_the_old_dependency(self):
        import numpy as np
        from train import dataset
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rows=self.fixture(root);options=dict(window_frames=150,negative_repeats=1,pcm_context=True)
            old=dataset(rows,root,positive_repeats=1,**options)
            explicit=dataset(rows,root,positive_repeats=1,stable_split_rng=False,**options)
            for split in old:
                for a,b in zip(old[split],explicit[split]):np.testing.assert_array_equal(a,b)
            changed=dataset(rows,root,positive_repeats=4,**options)
            self.assertFalse(np.array_equal(old['validation'][0],changed['validation'][0]))


if __name__=='__main__':unittest.main()
