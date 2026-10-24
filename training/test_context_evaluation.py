import unittest
import tempfile
import hashlib
from pathlib import Path
from evaluate_context import eligible, summarize, load


class ContextEvaluationTests(unittest.TestCase):
    def test_consumed_or_household_input_rejected_even_with_renamed_source(self):
        for field in ({'evaluation_only': True}, {'frozen_holdout': True}, {'source': 'private-family'}):
            with self.assertRaises(ValueError):
                eligible([dict(split='validation', label=1, **field)])

    def test_only_development_targets_selected(self):
        rows = [{'split': s, 'label': n} for s in ['train', 'validation', 'test'] for n in [0, 1]]
        self.assertEqual(eligible(rows), [{'split': 'validation', 'label': 1}])
        self.assertEqual(eligible(rows,True),
                         [{'split': 'validation', 'label': 0}, {'split': 'validation', 'label': 1}])

    def test_renamed_protected_recording_rejected_before_audio_decoding(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'renamed.wav';path.write_bytes(b'protected fixture bytes')
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError,'Protected audio'):
                load(dict(path=path.name,sha256=digest),path.parent,{digest})

    def test_background_windows_not_reported_as_target_hits_or_independent_events(self):
        cases = [dict(style='adult', condition='speech', target_peak=.8,
                      prefix_above_threshold_windows=12),
                 dict(style='adult', condition='speech', target_peak=.95,
                      prefix_above_threshold_windows=0)]
        self.assertEqual(summarize(cases)['adult/speech'],
                         {'targets': 2, 'hits': 1, 'prefix_above_threshold_windows': 12})

    def test_near_word_after_speech_counts_as_false_wake_not_hit(self):
        cases=[dict(style='adult',condition='speech',label=0,target_peak=.95,
                    prefix_above_threshold_windows=0)]
        self.assertEqual(summarize(cases)['adult/speech'],
                         {'targets':0,'hits':0,'non_targets':1,'false_wakes':1,
                          'prefix_above_threshold_windows':0})


if __name__ == '__main__':
    unittest.main()
