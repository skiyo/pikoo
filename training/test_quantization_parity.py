import unittest
import numpy as np
from check_quantization import eligible,errors


class QuantizationParityTest(unittest.TestCase):
    def test_only_original_train_and_balanced_sources_are_selected(self):
        rows=[{'split':'train','label':0,'source':'a'}]*3+[{'split':'train','label':1,'source':'b'},{'split':'validation','label':1,'source':'c'}]
        selected=eligible(rows)
        self.assertEqual([x['source'] for x in selected[:2]],['a','b'])
        self.assertTrue(all(x['split']=='train' for x in selected))
    def test_evaluation_or_frozen_audio_is_rejected_even_when_tagged_train(self):
        for flag in ['evaluation_only','frozen_holdout']:
            with self.assertRaisesRegex(ValueError,'Protected'):eligible([{'split':'train','source':'a','label':1,flag:True}])
    def test_export_collapse_is_visible_and_nonfinite_scores_rejected(self):
        self.assertGreater(errors([[0,.996],[.1,.996]])['max_absolute_error'],.99)
        self.assertLess(errors([[.1,.102],[.9,.898]])['mean_absolute_error'],.003)
        for pairs in [[],[[np.nan,.5]],[[1.1,.5]]]:
            with self.assertRaises(ValueError):errors(pairs)
    def test_brief_speech_spike_is_located_even_with_small_mean_error(self):
        pairs=[[.01,.01]]*100
        pairs[73]=[.93,.62]
        report=errors(pairs)
        self.assertLess(report['mean_absolute_error'],.03)
        self.assertGreater(report['max_absolute_error'],.15)
        self.assertEqual(report['worst_step'],73)
        self.assertEqual(report['float_at_worst'],.93)
        self.assertEqual(report['int8_at_worst'],.62)


if __name__=='__main__':unittest.main()
