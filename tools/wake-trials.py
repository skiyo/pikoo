#!/usr/bin/env python3
"""Guide real-person wake trials through an already owned USB monitor.

No raw recording, model training, or simulated wake commands. macOS spoken
instructions play only while the board is muted. The user says the wake phrase.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
import re
import signal
from pathlib import Path
import socket
import subprocess
import sys
import time
from check_wake_policy import validate as validate_policy
from monitor_control import registered_socket


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def trial_configuration(firmware, model, policy_path, test_report, diagnostic=False):
    """Formal Hi trials require completed, consumed full TEST evidence."""
    if not model and not policy_path:
        if not diagnostic:
            raise ValueError('Formal trials require the frozen Hi model and policy')
        return {'wake_phrase': '你好 Pikoo', 'pronunciation': 'legacy Chinese diagnostic only',
                'runtime_identity_required': False, 'policy_sha256': None}
    if not model or not policy_path:
        raise ValueError('Provide both wake model and policy')
    policy = validate_policy(model, json.loads(policy_path.read_text()), allow_trial=diagnostic)
    if firmware.get('model_sha256') != sha(model) or firmware.get('policy_sha256') != sha(policy_path):
        raise ValueError('Verified flash manifest differs from the frozen model/policy')
    version = firmware.get('firmware_version')
    if not isinstance(version, str) or not version:
        raise ValueError('Expected installed firmware version required')
    config = {'wake_phrase': 'Hi, Pikoo',
        'pronunciation': 'piku or piko' if policy['target']=='hi-piku-piko-v2' else 'piku only',
        'runtime_identity_required': True, 'model_sha256': sha(model),
        'policy_sha256': sha(policy_path), 'firmware_version': version}
    if diagnostic:
        return config
    if firmware.get('offline_qualified') is not True or not test_report:
        raise ValueError('Formal trials need explicit qualification and a full TEST report')
    report = json.loads(test_report.read_text())
    marker_path=policy_path.parent/'independent-TEST-consumption.json'
    if not marker_path.is_file():
        raise ValueError('Completed TEST consumption proof required')
    marker = json.loads(marker_path.read_text())
    required = sorted(policy.get('required_test_cohorts', []))
    expected = sorted(f'{age}:{accent}:{v}' for age,accent in
        [('adult','standard'),('adult','Chinese-accent'),('childlike','Chinese-accent')]
        for v in ('piku','piko'))
    metrics = report.get('metrics', {})
    groups = metrics.get('groups', {})
    if (policy.get('target')!='hi-piku-piko-v2' or required!=expected or
            report.get('status')!='mixed-independent-TEST-completed' or
            report.get('model_sha256')!=config['model_sha256'] or
            report.get('policy_sha256')!=config['policy_sha256'] or
            report.get('fixed_policy')!={k:policy[k] for k in ('rolling','threshold')} or
            any(metrics.get(k)!=policy[k] for k in ('rolling','threshold')) or
            report.get('cases')!=150 or report.get('real_child_TEST_cases')!=40 or
            report.get('family_TEST_only') is not True or
            report.get('model_or_policy_selected_using_TEST') is not False or
            metrics.get('passed') is not True or metrics.get('false_wakes')!=0 or
            metrics.get('early_wakes')!=0 or sorted(groups)!=required or
            any(g.get('targets')!=20 or type(g.get('hits')) is not int or not 18<=g['hits']<=20 for g in groups.values()) or
            type(metrics.get('latency_p95_ms')) not in (int,float) or not 0<=metrics['latency_p95_ms']<=800 or
            marker.get('status')!='completed-consumed' or marker.get('report_sha256')!=sha(test_report) or
            any(marker.get(k)!=report.get(k) or not report.get(k) for k in
                ('model_sha256','policy_sha256','protocol_sha256','manifest_sha256'))):
        raise ValueError('Complete matching six-cohort TEST and consumption proof required')
    if not re.fullmatch('[0-9a-f]{64}',firmware.get('app_sha256','')):
        raise ValueError('Verified installed application hash required')
    config['sealed_test_report_sha256'] = sha(test_report)
    config['app_sha256'] = firmware['app_sha256']
    return config


def runtime_identity(state, config):
    if config['runtime_identity_required'] and any(state.get(k)!=v for k,v in {
            'version':config['firmware_version'],'wake_model_sha':config['model_sha256'],
            'wake_policy_sha':config['policy_sha256']}.items()):
        raise RuntimeError('Running device version/model/policy differs; do not count these trials')


def isolated(state):
    if any(state.get(k)!=v for k,v in {'state':0,'muted':0,'upload':0,'wake_test':1}.items()):
        raise RuntimeError('Local trial isolation was not confirmed')


def before_cue(armed, state):
    isolated(state)
    if (state['wake_hits']!=armed['wake_hits'] or state['uploaded_samples']!=armed['uploaded_samples'] or
            state['uptime_ms']<armed['uptime_ms']):
        raise RuntimeError('Pre-cue activity cannot be credited to the target utterance; stop this run')


class Monitor:
    def __init__(self, socket_path, status_path):
        self.socket_path, self.status_path = socket_path, status_path

    def command(self, text):
        if text not in {'status', 'mute', 'unmute', 'wake test on', 'wake test off'}:
            raise ValueError('Trial tooling must never simulate a wake')
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(3)
            connection.connect(str(self.socket_path))
            connection.sendall((text + '\n').encode())
            reply = json.loads(connection.recv(8192))
            if reply.get('queued') != text:
                raise RuntimeError('Monitor did not queue requested trial command')
            return reply

    def state(self):
        started = time.time()
        reply = self.command('status')
        pid = reply.get('status',{}).get('pid')
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            result = json.loads(self.status_path.read_text())
            if not pid or result.get('pid')!=pid:
                raise RuntimeError('Status file belongs to another monitor')
            if result.get('observed_at', 0) >= started:
                return result['device']
            time.sleep(.05)
        raise RuntimeError('没有收到新的设备状态；请检查 USB 和监测工具')

    def settle(self, muted):
        self.command('mute' if muted else 'unmute')
        # Mute/unmute already request a session stop. Explicit `end` also
        # clears the persistent topic, which a wake trial must never do.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            state = self.state()
            if bool(state['muted']) == muted and state['state'] == (5 if muted else 0) and state.get('upload')==0:
                return state
            time.sleep(.1)
        raise RuntimeError('设备未回到所需的待机状态，停止测试')


def summarize(rows, expected, diagnostic=False, observer_confirmed=False):
    hits = sum(row.get('detected') is True for row in rows)
    target = math.ceil(expected * .9)
    clean = all(type(row.get(key)) is int and row[key]==0 for row in rows for key in
                ['wake_error_delta', 'wake_drop_delta', 'uploaded_sample_delta']) and all(
                    row.get('rebooted') is False and type(row.get('detected')) is bool for row in rows)
    criterion = expected==20 and len(rows)==20 and hits>=18 and clean
    return {'completed': len(rows), 'expected': expected, 'hits': hits,
            'required_hits': target, 'complete': len(rows) == expected, 'runtime_clean': clean,
            'diagnostic_only': diagnostic,
            'hit_criterion_met':criterion, 'observer_confirmed':observer_confirmed is True,
            'met_target':not diagnostic and criterion and observer_confirmed is True}


def arm_trial(monitor, config, number, ready, say, pause=time.sleep):
    """Wait for the human while muted, then show a silent listening cue."""
    monitor.settle(True)
    monitor.command('wake test on')
    if monitor.state().get('wake_test') != 1:
        raise RuntimeError('固件未启用本地评测隔离；请先升级相应固件')
    say(f'第{number}次。先不要说话，按回车准备，等绿色开始后再开口。')
    ready(number)
    pause(.8)
    armed = monitor.state()
    monitor.settle(False)
    pause(1)
    before = monitor.state()
    runtime_identity(before, config)
    before_cue(armed, before)
    return before


@contextmanager
def trial_session(monitor, leave_muted=False, on_cleanup=None):
    """Restore the requested microphone state even if the trial is interrupted."""
    signals = [signal.SIGHUP, signal.SIGTERM, signal.SIGINT]
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
            # Never remove the network gate while the microphone is live.
            # If either step fails, leave it muted/gated and report failure.
            monitor.settle(True)
            monitor.command('wake test off')
            if not leave_muted:
                monitor.settle(False)
            if on_cleanup:
                on_cleanup()
        finally:
            for number, handler in previous.items():
                signal.signal(number, handler)


def confirm_observation(report, observation, report_sha256):
    """Annotate a finished run after the human observes it; never alter trials."""
    if (not isinstance(report_sha256,str) or not re.fullmatch('[0-9a-f]{64}',report_sha256) or
            report.get('status')!='real-person-trials-complete' or
            report.get('cleanup_verified') is not True or report.get('diagnostic_only') is not False or
            report.get('offline_qualified') is not True or report.get('runtime_identity_verified') is not True or
            report.get('cloud_sessions_disabled_during_trials') is not True or
            observation.get('report_sha256')!=report_sha256 or
            observation.get('tester_id')!=report.get('tester_id') or
            observation.get('session_index')!=report.get('session_index') or
            not isinstance(observation.get('human_statement'),str) or not observation['human_statement'].strip() or
            type(observation.get('observed_at_unix')) not in (int,float) or
            not math.isfinite(observation['observed_at_unix']) or
            not observation['observed_at_unix']>=report['finished_at_unix']):
        raise ValueError('Post-run human observation must match this completed verified run')
    if report.get('observer_confirmed') is True:
        raise ValueError('Preserve the existing confirmed record; do not silently revise it')
    confirmed = (observation.get('all20_independent_complete_targets_once') is True and
                 observation.get('no_adult_follow_or_repeated_calls') is True and
                 observation.get('distance_m')==1)
    result = {**report, 'observer_confirmed':confirmed, 'observer_evidence':observation,
              'raw_run_report_sha256':report_sha256, 'formal_family_acceptance_passed':False}
    result['summary']=summarize(report['trials'],20,False,confirmed)
    return result


def family_summary(reports):
    expected={(person,session) for person in ('adult-1','adult-2','child-1','child-2') for session in (1,2)}
    if any(type(r.get('session_index')) is not int for r in reports):
        raise ValueError('Explicit numbered sessions required')
    keys={(r.get('tester_id'),r.get('session_index')) for r in reports}
    if len(reports)!=8 or keys!=expected:
        raise ValueError('All four people and two distinct20-trial sessions required')
    identities={(r.get('model_sha256'),r.get('policy_sha256'),r.get('app_sha256'),r.get('sealed_test_report_sha256')) for r in reports}
    if len(identities)!=1 or any(not isinstance(h,str) or not re.fullmatch('[0-9a-f]{64}',h) for h in next(iter(identities))):
        raise ValueError('All family runs must use the same verified model/policy/application')
    raw_hashes=[r.get('raw_run_report_sha256') for r in reports]
    if len(set(raw_hashes))!=8 or any(not isinstance(h,str) or not re.fullmatch('[0-9a-f]{64}',h) for h in raw_hashes):
        raise ValueError('Eight distinct original run reports required')
    windows=sorted((r['started_at_unix'],r['finished_at_unix']) for r in reports)
    if any(not math.isfinite(start) or not math.isfinite(end) or not start<end for start,end in windows) or any(a[1]>b[0] for a,b in zip(windows,windows[1:])):
        raise ValueError('Do not duplicate or overlap one device run as separate sessions')
    passed=True; results=[]
    for run in reports:
        if (run.get('status')!='real-person-trials-complete' or run.get('diagnostic_only') is not False or
                run.get('offline_qualified') is not True or run.get('runtime_identity_verified') is not True or
                run.get('cleanup_verified') is not True or run.get('tester_role_user_selected')!=run['tester_id'].split('-')[0]):
            raise ValueError('Only completed, verified, correctly attributed family runs allowed')
        observation=run.get('observer_evidence',{})
        original={**run,'observer_confirmed':False}
        verified=confirm_observation(original,observation,run.get('raw_run_report_sha256'))
        summary=verified['summary'];passed=passed and summary['met_target']
        results.append({'tester_id':run['tester_id'],'session_index':run['session_index'],**summary})
    return {'scope':'four-people-two-sessions-only','runs':results,
            'family_two_session_passed':passed,'formal_goal_completed':False,
            'eight_hour_background_passed':False,'hardware_resource_acceptance_implied':False}


def results_main(argv):
    parser=argparse.ArgumentParser(description='Record post-run observations or summarize eight private runs; no USB/audio')
    sub=parser.add_subparsers(dest='action',required=True)
    confirm=sub.add_parser('confirm');confirm.add_argument('--report',type=Path,required=True)
    confirm.add_argument('--observation',type=Path,required=True)
    family=sub.add_parser('family');family.add_argument('--run',type=Path,action='append',required=True)
    for command in (confirm,family):command.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv);os.umask(0o077)
    if args.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Keep raw family test results outside the source repository')
    if args.action=='confirm':
        value=confirm_observation(json.loads(args.report.read_text()),json.loads(args.observation.read_text()),sha(args.report))
    else:
        value=family_summary([json.loads(p.read_text()) for p in args.run])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as file:json.dump(value,file,ensure_ascii=False,indent=2)
    print(json.dumps({'written':True,'formal_goal_completed':False}))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--socket', type=Path, required=True)
    p.add_argument('--port', required=True, help='Must match this project\'s registered USB monitor')
    p.add_argument('--status-file', type=Path, required=True)
    p.add_argument('--firmware-manifest', type=Path, required=True)
    p.add_argument('--wake-model', type=Path)
    p.add_argument('--wake-policy', type=Path)
    p.add_argument('--sealed-test-report', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--tester', choices=['adult', 'child'], required=True, help='User-provided role; never inferred from voice')
    p.add_argument('--tester-id', choices=['adult-1','adult-2','child-1','child-2'])
    p.add_argument('--session-index', type=int, choices=[1,2])
    p.add_argument('--trials', type=int, default=20)
    p.add_argument('--ready', action='store_true', help='Use only after the human explicitly says they are ready')
    p.add_argument('--diagnostic',action='store_true',help='Explicit short engineering trial; never reports acceptance of an unqualified model')
    a = p.parse_args()
    if not 1 <= a.trials <= 100:
        raise ValueError('Invalid trial count')
    if not a.diagnostic and (a.trials!=20 or not a.tester_id or a.session_index is None):
        raise ValueError('Formal run requires20 trials, a tester ID and session1or2')
    if a.tester_id and not a.tester_id.startswith(a.tester+'-'):
        raise ValueError('Tester ID and user-declared adult/child role differ')
    firmware = json.loads(a.firmware_manifest.read_text())
    config = trial_configuration(firmware,a.wake_model,a.wake_policy,a.sealed_test_report,a.diagnostic)
    if a.output.exists():
        raise ValueError('Preserve the original result; choose a new private output file')
    if a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('Keep family trial results outside the source repository')
    if sys.platform != 'darwin':
        raise RuntimeError('Spoken guidance currently requires macOS')
    os.umask(0o077)
    if registered_socket(a.port)!=a.socket.resolve():
        raise RuntimeError('Use only this project\'s registered monitor for the selected port')
    import fcntl
    trial_lock = a.status_file.with_suffix('.wake-test.lock').open('a')
    try:
        fcntl.flock(trial_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('已有唤醒测试窗口，请先完成或关闭它；不会中断另一测试') from None
    monitor = Monitor(a.socket, a.status_file)
    report = {'status': 'real-person-trials-incomplete', 'tester_role_user_selected': a.tester,
              'distance': 'instructed 1 metre; not measured by software',
              'model_sha256_from_verified_flash_manifest': firmware['model_sha256'],
              'source_commit': firmware.get('source_commit'), 'started_at_unix': time.time(),
              'raw_audio_saved': False, 'training_performed': False,
              'cloud_sessions_disabled_during_trials': False, 'trials': []}
    report.update(diagnostic_only=a.diagnostic,offline_qualified=firmware.get('offline_qualified'),
                  frozen_candidate_identity=firmware.get('frozen_candidate_identity'),
                  tester_id=a.tester_id,session_index=a.session_index,
                  single_person_single_session=True, observer_confirmed=False,
                  cleanup_verified=False, formal_family_acceptance_passed=False, **config)
    a.output.parent.mkdir(parents=True, exist_ok=True)

    def say(text):
        subprocess.run(['/usr/bin/say', '-v', 'Tingting', '-r', '175', text], check=True)

    def save():
        report['summary'] = summarize(report['trials'], a.trials, a.diagnostic,
                                      report.get('observer_confirmed',False))
        temporary = a.output.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        temporary.chmod(0o600)
        temporary.replace(a.output)

    print('请将设备放在约一米处。每次绿色开始提示后，用平常音量说一次“'+config['wake_phrase']+'”（'+config['pronunciation']+'），自然连读，不用按 BOOT。')
    print('一轮请由同一位测试者完成；换人前先停止，再单独开始新一轮。')
    print('本工具开启本地评测，只统计唤醒，不连接语音服务器。不会保存录音或训练模型。')
    if a.diagnostic:print('本轮仅为工程短测，无论命中几次都不认定正式验收通过。')
    runtime_identity(monitor.state(),config)
    report['started_at_unix']=time.time()
    report['runtime_identity_verified']=config['runtime_identity_required']
    try:
        with trial_session(monitor, leave_muted=a.diagnostic,
                           on_cleanup=lambda: report.update(cleanup_verified=True)):
            monitor.settle(True)
            say('开始测试。看到绿色开始提示后，用平常音量读一次屏幕上的唤醒词，可以自然连读。')
            for number in range(1, a.trials + 1):
                report['current_attempt']=number
                def ready(number):
                    if not a.ready:
                        input(f'第{number}轮：按回车准备，随后等绿色“开始”再说（现在先别开口）：')
                before = arm_trial(monitor, config, number, ready, say)
                start = time.monotonic()
                print(f'\033[42m 第{number}次：开始 \033[0m',flush=True)
                peak = 0.
                after = before
                while time.monotonic() - start < 6:
                    after = monitor.state()
                    runtime_identity(after,config)
                    isolated(after)
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
            report['cloud_sessions_disabled_during_trials']=True
            say('本轮测试结束。麦克风将保持关闭。' if a.diagnostic else '本轮测试结束。设备即将恢复正常待机。')
    except (Exception, KeyboardInterrupt) as error:
        report['status']='interrupted-local-test'
        report['failure']={'type':type(error).__name__,'message':str(error),
                           'attempt':report.get('current_attempt'),
                           'uncompleted_attempt_not_counted_as_model_failure':True}
        raise
    finally:
        if not report['cleanup_verified']:
            report['status']='interrupted-or-cleanup-unverified'
        report['finished_at_unix']=time.time()
        save()
    print(json.dumps(report['summary'], ensure_ascii=False, indent=2))
    print('诊断结束，麦克风保持关闭。结果只保存在本机。' if a.diagnostic else '已经恢复正常待机。结果只保存在本机。')
    print('机器计数不等于真人验收；仍需核实每次独立完整发音、距离和两场结果。')


if __name__ == '__main__':
    try:
        if len(sys.argv)>1 and sys.argv[1] in ('confirm','family'):
            results_main(sys.argv[1:])
        else:main()
    except KeyboardInterrupt:
        print('\n测试已中止；已尝试清理测试状态。未完成的测试不计为通过。')
        sys.exit(130)
    except (RuntimeError, ValueError, OSError) as error:
        message=str(error)
        if 'Pre-cue activity' in message:
            message='绿色开始之前已经检测到活动，本轮未计分。下次请等绿色文字出现后再开口。'
        print('\n测试已停止：'+message)
        print('本轮未完成，不计为模型失败或通过；诊断细节已保存到私密结果。')
        sys.exit(2)
