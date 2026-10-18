import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec('tensorflow'),'Optional TensorFlow runtime not installed')
class StreamingWindowTest(unittest.TestCase):
    def test_initialization_scores_do_not_enter_first_valid_mean(self):
        from evaluate import rolling_peak
        self.assertEqual(rolling_peak([1.]*172+[0.]*5,519),0.)
        self.assertEqual(rolling_peak([1.]*172+[1.]*4,519),0.)
        self.assertEqual(rolling_peak([0.]*172+[1.]*5,519),1.)
    def test_later_false_wake_is_preserved_and_default_contract_unchanged(self):
        from evaluate import rolling_peak
        self.assertEqual(rolling_peak([0.]*177+[1.]*5,519),1.)
        self.assertEqual(rolling_peak([1.]*5),1.)
        self.assertEqual(rolling_peak([1.]*4),0.)
        with self.assertRaises(ValueError):rolling_peak([1.]*9,518)


if __name__=='__main__':unittest.main()
