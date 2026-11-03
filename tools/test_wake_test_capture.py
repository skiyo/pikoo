# SPDX-License-Identifier: Apache-2.0
import base64
from pathlib import Path
import subprocess
import sys
import unittest
from wake_test_capture import decode_capture


def diagnostic(**overrides):
    fields = dict(state=0, muted=0, upload=0, uploaded_samples=480,
                  frames=3, reconnects=1, uptime_ms=10000,
                  wake_errors=0, wake_dropped=0)
    fields.update(overrides)
    return 'I (1) diag: board=dualeye ' + ' '.join(f'{k}={v}' for k, v in fields.items())


def log():
    encoded = base64.b64encode(b'\x12\x34' * 160).decode()
    return [diagnostic(), 'I (2) wake_pcm: begin rate=16000 samples=64000',
            *(f'I (3) wake_pcm: seq={i} count=160 data={encoded}' for i in range(400)),
            'I (4) wake_pcm: done', diagnostic(uptime_ms=15000)]


class CaptureIntegrity(unittest.TestCase):
    def decode(self, lines):
        return decode_capture(('\n'.join(lines) + '\n').encode())

    def test_complete_log_keeps_exact_pcm_and_no_admission(self):
        pcm, proof = self.decode(log())
        self.assertEqual(pcm, b'\x12\x34' * 64000)
        self.assertEqual(proof['packets'], 400)
        self.assertFalse(proof['model_scored'])
        self.assertFalse(proof['TRAIN_or_calibration_or_model_selection_allowed'])
        self.assertFalse(proof['consent_or_freshness_or_content_proven_by_extraction'])

    def test_loss_duplication_and_truncation_are_rejected(self):
        complete = log()
        for broken in (complete[:44] + complete[45:], complete[:44] + complete[43:],
                       complete[:-2], complete[:-1], complete[1:]):
            with self.subTest(length=len(broken)), self.assertRaises(ValueError):
                self.decode(broken)

    def test_wrong_rate_count_and_base64_rejected(self):
        for index, text in ((1, 'wake_pcm: begin rate=24000 samples=64000'),
                            (2, 'wake_pcm: seq=0 count=160 data=%%'),
                            (2, 'wake_pcm: seq=0 count=1 data=AAAA')):
            lines = log(); lines[index] = text
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.decode(lines)

    def test_upload_and_hidden_intermediate_reconnect_rejected(self):
        for overrides in ({'upload': 1}, {'uploaded_samples': 481}, {'frames': 4},
                          {'reconnects': 2}, {'wake_errors': 1}, {'wake_dropped': 1},
                          {'state': 2}, {'muted': 1}, {'uptime_ms': 9000}):
            lines = log(); lines.insert(20, diagnostic(**overrides))
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.decode(lines)

    def test_multiple_captures_and_crashes_rejected(self):
        for lines in (log() + log(), log()[:20] + ['ESP-ROM: esp32s3'] + log()[20:]):
            with self.assertRaises(ValueError):
                self.decode(lines)

    def test_incomplete_diagnostic_rejected(self):
        lines = log(); lines[-1] = 'diag: board=dualeye state=0'
        with self.assertRaises(ValueError):
            self.decode(lines)

    def test_cli_refuses_audio_output_inside_repository_before_reading_log(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, str(root / 'tools/wake_test_capture.py'),
            '--private-log', str(root / 'absent-private-log'), '--output',
            str(root / 'forbidden-TEST-audio')], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertIn('outside the source repository', result.stderr)
        self.assertFalse((root / 'forbidden-TEST-audio').exists())


if __name__ == '__main__':
    unittest.main()
