#!/usr/bin/env python3
"""Guide real-person wake trials through an already owned USB monitor.

No raw recording, model training, or simulated wake commands. macOS spoken
instructions play only while the board is muted. The user says the wake phrase.
"""
import argparse
from contextlib import contextmanager
import json
import math
import os
import signal
from pathlib import Path
import socket
import subprocess
import sys
import time


class Monitor:
    def __init__(self, socket_path, status_path):
        self.socket_path, self.status_path = socket_path, status_path

    def command(self, text):
        if text not in {'status', 'mute', 'unmute', 'end', 'wake test on', 'wake test off'}:
            raise ValueError('Trial tooling must never simulate a wake')
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(3)
            connection.connect(str(self.socket_path))
            connection.sendall((text + '\n').encode())
            connection.recv(8192)

    def state(self):
        started = time.time()
        self.command('status')
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            result = json.loads(self.status_path.read_text())
            if result.get('observed_at', 0) >= started:
                return result['device']
            time.sleep(.05)
        raise RuntimeError('没有收到新的设备状态；请检查 USB 和监测工具')

    def settle(self, muted):
        self.command('mute' if muted else 'unmute')
        self.command('end')
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            state = self.state()
            if bool(state['muted']) == muted and state['state'] == (5 if muted else 0):
                return state
            time.sleep(.1)
        raise RuntimeError('设备未回到所需的待机状态，停止测试')


def summarize(rows, expected):
    hits = sum(bool(row['detected']) for row in rows)
    target = math.ceil(expected * .9)
    clean = all(not row.get(key, 0) for row in rows for key in
                ['wake_error_delta', 'wake_drop_delta', 'uploaded_sample_delta', 'rebooted'])
    return {'completed': len(rows), 'expected': expected, 'hits': hits,
            'required_hits': target, 'complete': len(rows) == expected, 'runtime_clean': clean,
            'met_target': len(rows) == expected and hits >= target and clean}


@contextmanager
def trial_session(monitor):
    """Restore standby on window close, interruption, or result-write failure."""
    signals = [signal.SIGHUP, signal.SIGTERM]
    previous = {number: signal.getsignal(number) for number in signals}

    def interrupted(number, frame):
        raise KeyboardInterrupt

    for number in signals:
        signal.signal(number, interrupted)
    try:
        yield
    finally:
        # A second close signal must not interrupt the bounded cleanup itself.
        for number in signals:
            signal.signal(number, signal.SIG_IGN)
        try:
            try:
                monitor.command('wake test off')
            finally:
                monitor.settle(False)
        finally:
            for number, handler in previous.items():
                signal.signal(number, handler)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--socket', type=Path, required=True)
    p.add_argument('--status-file', type=Path, required=True)
    p.add_argument('--firmware-manifest', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--tester', choices=['adult', 'child'], required=True, help='User-provided role; never inferred from voice')
    p.add_argument('--trials', type=int, default=20)
    p.add_argument('--ready', action='store_true', help='Use only after the human explicitly says they are ready')
    a = p.parse_args()
    if not 1 <= a.trials <= 100:
        raise ValueError('Invalid trial count')
    if sys.platform != 'darwin':
        raise RuntimeError('Spoken guidance currently requires macOS')
    os.umask(0o077)
    import fcntl
    trial_lock = a.status_file.with_suffix('.wake-test.lock').open('a')
    try:
        fcntl.flock(trial_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('已有唤醒测试窗口，请先完成或关闭它；不会中断另一测试') from None
    monitor = Monitor(a.socket, a.status_file)
    firmware = json.loads(a.firmware_manifest.read_text())
    report = {'status': 'real-person-trials-incomplete', 'tester_role_user_selected': a.tester,
              'distance': 'instructed 1 metre; not measured by software',
              'model_sha256_from_verified_flash_manifest': firmware['model_sha256'],
              'source_commit': firmware['source_commit'], 'started_at_unix': time.time(),
              'raw_audio_saved': False, 'training_performed': False,
              'cloud_sessions_disabled_during_trials': True, 'trials': []}
    a.output.parent.mkdir(parents=True, exist_ok=True)

    def say(text):
        subprocess.run(['/usr/bin/say', '-v', 'Tingting', '-r', '175', text], check=True)

    def save():
        report['summary'] = summarize(report['trials'], a.trials)
        temporary = a.output.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        temporary.chmod(0o600)
        temporary.replace(a.output)

    print('请将设备放在约一米处。每次短音后，用平常音量说一次“你好皮酷”，不用按 BOOT。')
    print('一轮请由同一位测试者完成；换人前先停止，再单独开始新一轮。')
    print('本工具开启本地评测，只统计唤醒，不连接语音服务器。不会保存录音或训练模型。')
    if not a.ready:
        input('准备好后按回车开始；现在不方便可直接关闭窗口。')
    with trial_session(monitor):
        try:
            monitor.settle(True)
            say('开始唤醒测试。每次短音后，只说一次，你好皮酷。')
            for number in range(1, a.trials + 1):
                monitor.settle(True)
                monitor.command('wake test on')
                if monitor.state().get('wake_test') != 1:
                    raise RuntimeError('固件未启用本地评测隔离；请先升级相应固件')
                say(f'第{number}次，准备。')
                time.sleep(.8)  # Let computer speech/reverberation finish while still muted.
                monitor.settle(False)
                time.sleep(1)
                before = monitor.state()
                start = time.monotonic()
                subprocess.run(['/usr/bin/afplay', '/System/Library/Sounds/Pop.aiff'], check=True)
                peak = 0.
                after = before
                while time.monotonic() - start < 6:
                    after = monitor.state()
                    peak = max(peak, after.get('wake_peak', 0))
                    if after['wake_hits'] > before['wake_hits']:
                        break
                    time.sleep(.08)
                detected = after['wake_hits'] > before['wake_hits']
                elapsed = round((time.monotonic() - start) * 1000)
                monitor.settle(True)
                report['trials'].append({'trial': number, 'detected': detected,
                    'time_after_cue_ms': elapsed, 'peak_score': peak,
                    'wake_error_delta': after['wake_errors'] - before['wake_errors'],
                    'wake_drop_delta': after['wake_dropped'] - before['wake_dropped'],
                    'uploaded_sample_delta': after['uploaded_samples'] - before['uploaded_samples'],
                    'rebooted': after['uptime_ms'] < before['uptime_ms']})
                save()
                if after['uploaded_samples'] != before['uploaded_samples'] or after.get('wake_test') != 1:
                    raise RuntimeError('本地评测隔离中断，已停止测试')
                print(f'{number}/{a.trials}：' + ('识别到了' if detected else '本次未识别'), flush=True)
                say('识别到了。' if detected else '这次未识别。')
            report['status'] = 'real-person-trials-complete'
            say('本轮测试结束。设备即将恢复正常待机。')
        finally:
            save()
    print(json.dumps(report['summary'], ensure_ascii=False, indent=2))
    print('已经恢复正常待机。结果只保存在本机。')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n测试已中止；已尝试恢复普通待机。未完成的测试不计为通过。')
        sys.exit(130)
