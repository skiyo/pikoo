import unittest
from ensemble_runtime import Agreement


class Tests(unittest.TestCase):
    def test_single_network_cannot_wake(self):
        detector=Agreement();self.assertEqual(max(detector.step(1,0) for _ in range(20)),0)
    def test_past_coincidence_accepts_small_offset(self):
        detector=Agreement();scores=[]
        for i in range(25):scores.append(detector.step(float(3<=i<9),float(7<=i<13)))
        self.assertGreaterEqual(max(scores),.8)
    def test_separate_utterance_peaks_cannot_vote_together(self):
        detector=Agreement();scores=[]
        for i in range(45):scores.append(detector.step(float(3<=i<9),float(25<=i<31)))
        self.assertLess(max(scores),.8)
    def test_rolling_warmup_and_reset_is_independent(self):
        detector=Agreement()
        self.assertEqual([detector.step(1,1) for _ in range(4)],[0]*4)
        self.assertEqual(detector.step(1,1),1)
        self.assertEqual(Agreement().step(1,1),0)
    def test_explicit_asymmetric_cutoffs_do_not_lower_either_requirement(self):
        detector=Agreement(.9,secondary_threshold=.92)
        self.assertLess(max(detector.step(.95,.91) for _ in range(20)),.9)
        detector=Agreement(.9,secondary_threshold=.92)
        self.assertLess(max(detector.step(.89,.99) for _ in range(20)),.9)
        detector=Agreement(.9,secondary_threshold=.92)
        self.assertGreaterEqual(max(detector.step(.91,.93) for _ in range(20)),.9)
    def test_default_decision_score_remains_exact(self):
        detector=Agreement()
        for _ in range(5):score=detector.step(.91,.93)
        self.assertEqual(score,sum([.91]*5)/5)


if __name__=='__main__':unittest.main()
