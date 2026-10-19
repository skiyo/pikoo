import importlib.util
import os
from pathlib import Path
import signal
import unittest
from unittest.mock import Mock, call

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

    def test_diagnostic_short_trial_never_claims_acceptance(self):
        for count in [3,20]:
            result=module.summarize([{'detected':True}]*count,count,diagnostic=True)
            self.assertEqual(result['hits'],count)
            self.assertTrue(result['complete'])
            self.assertTrue(result['diagnostic_only'])
            self.assertFalse(result['met_target'])

    def test_diagnostic_cleanup_keeps_microphone_closed_even_on_interrupt(self):
        monitor=Mock()
        with self.assertRaises(KeyboardInterrupt):
            with module.trial_session(monitor,leave_muted=True):
                raise KeyboardInterrupt
        self.assertEqual(monitor.mock_calls,[call.command('wake test off'),call.settle(True)])

    def test_window_close_restores_standby_and_signal_handlers(self):
        for number in [signal.SIGHUP, signal.SIGTERM]:
            with self.subTest(signal=number):
                monitor = Mock()
                previous = signal.getsignal(number)
                with self.assertRaises(KeyboardInterrupt):
                    with module.trial_session(monitor):
                        os.kill(os.getpid(), number)
                self.assertEqual(monitor.mock_calls,
                                 [call.command('wake test off'), call.settle(False)])
                self.assertEqual(signal.getsignal(number), previous)

    def test_result_write_or_disable_failure_still_restores_standby(self):
        monitor = Mock()
        with self.assertRaises(OSError):
            with module.trial_session(monitor):
                raise OSError('result disk unavailable')
        monitor.settle.assert_called_once_with(False)
        monitor = Mock()
        monitor.command.side_effect = OSError('command unavailable')
        with self.assertRaises(OSError):
            with module.trial_session(monitor):
                pass
        monitor.settle.assert_called_once_with(False)


if __name__ == '__main__':
    unittest.main()
