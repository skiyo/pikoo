#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""One explicitly requested, local-only four-second TEST recording.

Requires an existing owned USB monitor with a private raw log. No flashing,
server/volume/topic changes, old-model selection or automatic capture loop.
The microphone stays MUTED on exit, including cancellation/failure.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import sys
import time
import wave

from monitor_control import registered_socket, command
from wake_test_capture import decode_capture

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = {'status', 'mute', 'unmute', 'wake test on', 'wake test off', 'wake capture'}


def case_config(plan, policy, policy_sha256, case_id, protocol_path, output):
    sys.path.insert(0, str(ROOT / 'training'))
    from wake_mixed_test import protocol
    if plan != protocol(policy, policy_sha256, plan['protected_registry_sha256'], plan['declared_at']):
        raise ValueError('Unchanged predeclared TEST protocol required before capture')
    slot = next((s for s in plan['slots'] if s['id'] == case_id), None)
    if slot is None or slot['source_kind'] != 'family':
        raise ValueError('Choose a predeclared family TEST slot, not a synthetic source')
    if output.resolve() != protocol_path.resolve().parent / 'captures' / case_id:
        raise ValueError('Capture output must be this protocol\'s private captures/case-ID directory')
    return slot


def private_file(path):
    info = path.stat()
    if (info.st_uid != os.getuid() or not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077):
        raise ValueError('Owned private monitor log/status files required')


class Monitor:
    def __init__(self, port, raw_log):
        self.target = registered_socket(port)
        if self.target is None:
            raise ValueError('Start this project\'s USB monitor first; no port is opened here')
        self.log = raw_log.resolve()
        self.status = self.log.with_suffix('.status.json')
        private_file(self.log); private_file(self.status)

    def send(self, value):
        if value not in COMMANDS:
            raise ValueError('Capture tooling forbids wake/end/volume/flash commands')
        reply = command(self.target, value)
        if reply.get('queued') != value:
            raise RuntimeError('Monitor did not accept command')
        return reply

    def state(self):
        started = time.time()
        reply = self.send('status')
        pid = reply.get('status', {}).get('pid')
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            record = json.loads(self.status.read_text())
            if record.get('pid') != pid or not pid:
                raise ValueError('Raw log/status do not belong to this USB monitor')
            if record.get('observed_at', 0) >= started:
                return record['device']
            time.sleep(.05)
        raise TimeoutError('No fresh device status; capture was not verified')

    def settle(self, muted):
        self.send('mute' if muted else 'unmute')
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            item = self.state()
            if (item.get('state') == (5 if muted else 0) and
                    item.get('muted') == int(muted) and item.get('upload') == 0):
                return item
            time.sleep(.05)
        raise TimeoutError('Device did not settle; no capture allowed')


def isolated_idle(item):
    if any(item.get(k) != v for k, v in
           {'state': 0, 'muted': 0, 'upload': 0, 'wake_test': 1}.items()):
        raise RuntimeError('Local TEST gate was not confirmed; refusing capture')


@contextmanager
def local_session(monitor):
    """Arm the offline gate while muted; always mute before disabling it."""
    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGHUP)}

    def interrupted(*_):
        raise KeyboardInterrupt

    for sig in previous:
        signal.signal(sig, interrupted)
    touched = False
    try:
        item = monitor.state()
        if item.get('state') not in (0, 5) or item.get('upload') != 0:
            raise RuntimeError('Active conversation: finish it yourself before TEST capture')
        touched = True
        monitor.settle(True)
        monitor.send('wake test on')
        if monitor.state().get('wake_test') != 1:
            raise RuntimeError('Firmware did not enable the offline TEST gate')
        yield
    finally:
        for sig in previous:
            signal.signal(sig, signal.SIG_IGN)
        try:
            # If muting fails, never remove the network-isolation gate.
            if touched:
                monitor.settle(True)
                monitor.send('wake test off')
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)


def collect_one(monitor, ready, cue, timeout=10):
    """Callbacks allow readiness/cue simulation in tests, never simulated PCM."""
    with local_session(monitor):
        ready()  # Explicit human readiness, while microphone is muted.
        # The person may have waited longer than the firmware's five-minute
        # test lease. Renew while still muted before the four-second window.
        monitor.send('wake test on')
        if monitor.state().get('wake_test') != 1:
            raise RuntimeError('Offline TEST gate expired; refusing capture')
        start = monitor.log.stat().st_size
        before = monitor.settle(False)
        isolated_idle(before)
        monitor.send('wake capture')
        deadline = time.monotonic() + timeout
        announced = False
        while time.monotonic() < deadline:
            with monitor.log.open('rb') as source:
                source.seek(start)
                raw = source.read(512 * 1024 + 1)
            if len(raw) > 512 * 1024:
                raise ValueError('Bounded capture log exceeded expected size')
            if b'wake_pcm: begin rate=16000 samples=64000' in raw and not announced:
                cue()  # Visual only: do not play synthetic guidance into TEST audio.
                announced = True
            if b'wake_pcm: done' in raw:
                isolated_idle(monitor.state())
                with monitor.log.open('rb') as source:
                    source.seek(start)
                    raw = source.read(512 * 1024 + 1)
                pcm, proof = decode_capture(raw)
                proof['old_model_scores_ignored'] = True
                return raw, pcm, proof
            time.sleep(.05)
        raise TimeoutError('Bounded capture did not finish; do not label as a TEST success')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('port', 'case-id'):
        p.add_argument('--' + name, required=True)
    for name in ('private-log', 'model', 'policy', 'protocol', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--ready', action='store_true', help='Only after explicit human readiness')
    a = p.parse_args()
    if a.output.resolve().is_relative_to(ROOT) or a.output.exists():
        p.error('Choose a NEW private directory outside the repository')
    if not a.ready and not sys.stdin.isatty():
        p.error('Interactive readiness or explicitly confirmed --ready required')
    from check_wake_policy import validate
    policy = validate(a.model, json.loads(a.policy.read_text()))
    if not policy.get('source_native_freeze_sha256') or not policy.get('micro_proof_sha256'):
        raise ValueError('Native-qualified freeze and parity proof required before TEST capture')
    policy_sha256 = hashlib.sha256(a.policy.read_bytes()).hexdigest()
    protocol_sha256 = hashlib.sha256(a.protocol.read_bytes()).hexdigest()
    slot = case_config(json.loads(a.protocol.read_text()), policy, policy_sha256,
                       a.case_id, a.protocol, a.output)
    now = datetime.now(timezone.utc)
    if datetime.fromisoformat(policy['candidate_frozen_at']) >= now:
        raise ValueError('Capture must be strictly after candidate freeze')
    os.umask(0o077)
    monitor = Monitor(a.port, a.private_log)
    lock_path = monitor.status.with_suffix('.wake-test.lock')
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        a.output.mkdir(mode=0o700, parents=True, exist_ok=False)
        metadata = {'status': 'planned-not-captured', 'started_at': now.isoformat(),
            'model_sha256': policy['model_sha256'],
            'policy_sha256': policy_sha256, 'protocol_sha256': protocol_sha256,
            'test_slot_id': a.case_id,
            'speaker_id': slot['speaker'], 'speaker_role_user_declared': slot['role'],
            'prompt': slot['prompt'], 'actual_content_label': None, 'split': 'test',
            'evaluation_only': True, 'frozen_holdout': True, 'family_inputs_used': True,
            'synthetic': False, 'real_child': slot['role'] == 'child',
            'training_or_tuning_allowed': False, 'model_scored': False}
        output = a.output / 'capture.json'
        output.write_text(json.dumps(metadata, indent=2) + '\n')

        def ready():
            if not a.ready:
                input('麦克风已关闭。准备好后按回车；看到“开始”后只说一次完整短句：')

        try:
            raw, pcm, proof = collect_one(monitor, ready,
                lambda: print('开始：' + slot['prompt'] + '（4秒，只说一遍）', flush=True))
            (a.output / 'capture.log').write_bytes(raw)
            with wave.open(str(a.output / 'TEST-only.wav'), 'wb') as audio:
                audio.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
                audio.writeframes(pcm)
            metadata.update(status='captured-unlabelled-not-scored',
                completed_at=datetime.now(timezone.utc).isoformat(), transport=proof)
        except BaseException:
            metadata['status'] = 'failed-or-interrupted-not-admitted'
            raise
        finally:
            output.write_text(json.dumps(metadata, indent=2) + '\n')
            print('采音已停止；已尝试保持麦克风关闭。未上传、未评分。', flush=True)


if __name__ == '__main__':
    main()
