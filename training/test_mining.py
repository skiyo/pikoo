import importlib.util
from pathlib import Path
import tempfile
import unittest
import wave


AVAILABLE = all(importlib.util.find_spec(n) for n in ('tensorflow', 'numpy', 'pymicro_features'))


@unittest.skipUnless(AVAILABLE, 'Optional training runtime')
class TrainingMiningTest(unittest.TestCase):
    def test_only_training_non_targets_can_be_mined(self):
        from mine_training_negatives import mining_rows
        rows = [dict(split=s, label=l) for s in ('train', 'validation', 'test') for l in (0, 1)]
        self.assertEqual(mining_rows(rows), [dict(split='train', label=0)])

    def test_mined_child_non_targets_are_repeated_without_expanding_other_child_rows(self):
        import numpy as np
        from train import dataset
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with wave.open(str(root / 'fixture.wav'), 'wb') as audio:
                audio.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
                audio.writeframes(np.zeros(8000, dtype='<i2').tobytes())
            row = dict(path='fixture.wav', label=0, split='train', group='fixture', real_child=True)
            ordinary = dataset([row], root, hard_negative_repeats=8)
            hard = dataset([{**row, 'hard_negative': True}], root, hard_negative_repeats=8)
            self.assertEqual(len(ordinary['train'][1]), 101)
            self.assertEqual(len(hard['train'][1]), 108)


if __name__ == '__main__':
    unittest.main()
