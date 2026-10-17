import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('wake_trials', Path(__file__).with_name('wake-trials.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class WakeTrialTest(unittest.TestCase):
    def test_incomplete_run_never_claims_acceptance(self):
        result = module.summarize([{'detected': True}] * 19, 20)
        self.assertFalse(result['complete'])
        self.assertFalse(result['met_target'])
        self.assertTrue(module.summarize([{'detected': True}] * 18 + [{'detected': False}] * 2, 20)['met_target'])
        self.assertFalse(module.summarize([{'detected': True}] * 17 + [{'detected': False}] * 3, 20)['met_target'])
        rows = [{'detected': True} for _ in range(20)]
        rows[0]['uploaded_sample_delta'] = 640
        self.assertFalse(module.summarize(rows, 20)['met_target'])

    def test_trial_tool_cannot_inject_manual_or_synthetic_wake(self):
        monitor = module.Monitor(Path('/unused'), Path('/unused'))
        for command in ['wake', 'takeover', 'wake capture', 'tone']:
            with self.subTest(command=command):
                with self.assertRaisesRegex(ValueError, 'never simulate a wake'):
                    monitor.command(command)


if __name__ == '__main__':
    unittest.main()
