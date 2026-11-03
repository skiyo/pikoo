# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import patch

from test_wake_test_capture import log, diagnostic
from wake_test_session import Monitor, collect_one, private_file


class FakeMonitor:
    """Explicit fake hardware; writes generated fixture PCM, never a microphone."""
    def __init__(self, root):
        self.log = Path(root) / 'fake.log'
        self.log.write_bytes(b'')
        self.commands = []
        self.muted = False
        self.gate = 0
        self.uptime = 10000
        self.active = False
        self.fail_arm = False
        self.fail_cleanup = False
        self.bad_upload = False

    def send(self, command):
        self.commands.append(command)
        if command == 'wake test on' and not self.fail_arm:
            self.gate = 1
        if command == 'wake test off':
            self.gate = 0
        if command == 'wake capture':
            with self.log.open('a') as output:
                output.write('\n'.join(log()[1:-1]) + '\n')

    def state(self):
        self.uptime += 1
        item = {'state': 2 if self.active else 5 if self.muted else 0,
                'muted': int(self.muted), 'upload': int(self.active or self.bad_upload),
                'wake_test': self.gate, 'uptime_ms': self.uptime}
        with self.log.open('a') as output:
            output.write(diagnostic(**{k: v for k, v in item.items() if k != 'wake_test'}) + '\n')
        return item

    def settle(self, muted):
        self.commands.append('mute' if muted else 'unmute')
        if self.fail_cleanup and muted and 'wake capture' in self.commands:
            raise OSError('fake USB loss during cleanup')
        self.muted = muted
        return self.state()


class CaptureSessionSafety(unittest.TestCase):
    def test_one_capture_has_gate_and_readiness_before_pcm_then_mutes(self):
        with tempfile.TemporaryDirectory() as root:
            monitor = FakeMonitor(root)
            stages = []
            def ready():
                self.assertTrue(monitor.muted)
                self.assertEqual(monitor.gate, 1)
                self.assertNotIn('wake capture', monitor.commands)
                stages.append('ready')
            raw, pcm, proof = collect_one(monitor, ready, lambda: stages.append('cue'))
            self.assertEqual(stages, ['ready', 'cue'])
            self.assertEqual(len(pcm), 128000)
            self.assertIn(b'wake_pcm: done', raw)
            self.assertFalse(proof['model_scored'])
            self.assertEqual(monitor.commands,
                ['mute', 'wake test on', 'wake test on', 'unmute', 'wake capture', 'mute', 'wake test off'])
            self.assertTrue(monitor.muted)
            self.assertEqual(monitor.gate, 0)

    def test_declined_readiness_never_captures(self):
        with tempfile.TemporaryDirectory() as root:
            monitor = FakeMonitor(root)
            def declined():
                raise KeyboardInterrupt
            with self.assertRaises(KeyboardInterrupt):
                collect_one(monitor, declined, lambda: self.fail('No cue expected'))
            self.assertNotIn('wake capture', monitor.commands)
            self.assertNotIn('unmute', monitor.commands)
            self.assertTrue(monitor.muted)
            self.assertEqual(monitor.gate, 0)

    def test_active_call_is_not_interrupted_by_preflight(self):
        with tempfile.TemporaryDirectory() as root:
            monitor = FakeMonitor(root); monitor.active = True
            with self.assertRaisesRegex(RuntimeError, 'Active conversation'):
                collect_one(monitor, lambda: self.fail(), lambda: self.fail())
            self.assertEqual(monitor.commands, [])

    def test_unconfirmed_gate_or_upload_change_never_counts_as_success(self):
        for attr in ('fail_arm', 'bad_upload'):
            with self.subTest(attr=attr), tempfile.TemporaryDirectory() as root:
                monitor = FakeMonitor(root)
                if attr == 'fail_arm': monitor.fail_arm = True
                def ready():
                    if attr == 'bad_upload': monitor.bad_upload = True
                with self.assertRaises(RuntimeError):
                    collect_one(monitor, ready, lambda: self.fail())
                self.assertNotIn('wake capture', monitor.commands)
                self.assertTrue(monitor.muted)

    def test_cleanup_failure_keeps_offline_gate_and_restores_signal_handlers(self):
        with tempfile.TemporaryDirectory() as root:
            monitor = FakeMonitor(root); monitor.fail_cleanup = True
            handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGHUP, signal.SIGTERM)}
            with self.assertRaises(OSError):
                collect_one(monitor, lambda: None, lambda: None)
            self.assertNotIn('wake test off', monitor.commands)
            self.assertEqual(monitor.gate, 1)
            for sig, handler in handlers.items():
                self.assertEqual(signal.getsignal(sig), handler)

    def test_tool_has_no_end_wake_flash_or_volume_command(self):
        monitor = Monitor.__new__(Monitor)
        with patch('wake_test_session.command') as send:
            for text in ('end', 'wake', 'tone', 'volume 0', 'write_flash', 'takeover'):
                with self.subTest(text=text), self.assertRaises(ValueError):
                    monitor.send(text)
            send.assert_not_called()

    def test_public_log_and_missing_owned_monitor_fail_before_capture(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'log'; path.write_bytes(b'')
            path.chmod(0o644)
            with self.assertRaises(ValueError): private_file(path)
            path.chmod(0o600); private_file(path)
            with patch('wake_test_session.registered_socket', return_value=None):
                with self.assertRaisesRegex(ValueError, 'monitor first'):
                    Monitor('/not-a-real-device', path)

    def test_gate_lease_is_renewed_after_long_human_readiness_wait(self):
        with tempfile.TemporaryDirectory() as root:
            monitor = FakeMonitor(root)
            def ready(): monitor.gate = 0  # Simulated lease expiry, no wall-clock wait.
            collect_one(monitor, ready, lambda: None)
            self.assertEqual(monitor.commands.count('wake test on'), 2)
            self.assertTrue(monitor.muted)


if __name__ == '__main__': unittest.main()
