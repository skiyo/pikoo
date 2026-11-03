import importlib.util
import os
import copy
import hashlib
import json
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import Mock, call
from check_wake_policy import frontend_fingerprint

spec = importlib.util.spec_from_file_location('wake_trials', Path(__file__).with_name('wake-trials.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def rows(hits=18,count=20):
    return [dict(detected=i<hits,wake_error_delta=0,wake_drop_delta=0,
                 uploaded_sample_delta=0,rebooted=False) for i in range(count)]


class WakeTrialTest(unittest.TestCase):
    def test_incomplete_run_never_claims_acceptance(self):
        result = module.summarize(rows(19,19), 20, observer_confirmed=True)
        self.assertFalse(result['complete'])
        self.assertFalse(result['met_target'])
        self.assertTrue(module.summarize(rows(),20,observer_confirmed=True)['met_target'])
        self.assertFalse(module.summarize(rows(17),20,observer_confirmed=True)['met_target'])
        trial_rows=rows(20);trial_rows[0]['uploaded_sample_delta']=640
        self.assertFalse(module.summarize(trial_rows,20,observer_confirmed=True)['met_target'])

    def test_missing_metrics_unconfirmed_and_short_runs_never_pass(self):
        self.assertFalse(module.summarize([{'detected':True}]*20,20,observer_confirmed=True)['met_target'])
        self.assertTrue(module.summarize(rows(),20)['hit_criterion_met'])
        self.assertFalse(module.summarize(rows(),20)['met_target'])
        self.assertFalse(module.summarize(rows(3,3),3,observer_confirmed=True)['met_target'])

    def test_trial_tool_cannot_inject_manual_or_synthetic_wake(self):
        monitor = module.Monitor(Path('/unused'), Path('/unused'))
        for command in ['wake', 'takeover', 'wake capture', 'tone', 'end']:
            with self.subTest(command=command):
                with self.assertRaisesRegex(ValueError, 'never simulate a wake'):
                    monitor.command(command)

    def test_settle_preserves_context_by_never_sending_end(self):
        for muted in (False, True):
            monitor = module.Monitor(Path('/unused'), Path('/unused'))
            monitor.command = Mock()
            monitor.state = Mock(return_value={'muted': int(muted), 'state': 5 if muted else 0,'upload':0})
            monitor.settle(muted)
            monitor.command.assert_called_once_with('mute' if muted else 'unmute')

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
        self.assertEqual(monitor.mock_calls,[call.settle(True),call.command('wake test off')])

    def test_window_close_restores_standby_and_signal_handlers(self):
        for number in [signal.SIGHUP, signal.SIGTERM, signal.SIGINT]:
            with self.subTest(signal=number):
                monitor = Mock()
                previous = signal.getsignal(number)
                with self.assertRaises(KeyboardInterrupt):
                    with module.trial_session(monitor):
                        os.kill(os.getpid(), number)
                self.assertEqual(monitor.mock_calls,
                                 [call.settle(True),call.command('wake test off'), call.settle(False)])
                self.assertEqual(signal.getsignal(number), previous)

    def test_result_write_or_disable_failure_still_restores_standby(self):
        monitor = Mock()
        with self.assertRaises(OSError):
            with module.trial_session(monitor):
                raise OSError('result disk unavailable')
        self.assertEqual(monitor.settle.call_args_list,[call(True),call(False)])
        monitor = Mock()
        monitor.command.side_effect = OSError('command unavailable')
        with self.assertRaises(OSError):
            with module.trial_session(monitor):
                pass
        monitor.settle.assert_called_once_with(True)

    def test_failed_mute_never_disables_network_isolation_gate(self):
        monitor=Mock();monitor.settle.side_effect=OSError('USB unavailable')
        with self.assertRaises(OSError):
            with module.trial_session(monitor):pass
        monitor.command.assert_not_called()

    def test_pre_cue_activity_or_wrong_model_cannot_count_as_target_hit(self):
        before={'state':0,'muted':0,'upload':0,'wake_test':1,'wake_hits':3,'uploaded_samples':0,'uptime_ms':1000}
        module.before_cue(before,{**before,'uptime_ms':2000})
        for change in ({'wake_hits':4},{'uploaded_samples':160},{'wake_test':0},{'uptime_ms':500}):
            with self.subTest(change=change),self.assertRaises(RuntimeError):
                module.before_cue(before,{**before,**change})
        config={'runtime_identity_required':True,'firmware_version':'test','model_sha256':'a'*64,'policy_sha256':'b'*64}
        state={'version':'test','wake_model_sha':'a'*64,'wake_policy_sha':'b'*64}
        module.runtime_identity(state,config)
        with self.assertRaises(RuntimeError):module.runtime_identity({**state,'wake_model_sha':'wrong'},config)


class FormalEvidenceTest(unittest.TestCase):
    def test_formal_requires_completed_bound_full_test_and_hi_target(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);model=root/'model.fixture';model.write_bytes(b'not-an-inference-model-fixture')
            groups=sorted(f'{a}:{c}:{v}' for a,c in [('adult','standard'),('adult','Chinese-accent'),('childlike','Chinese-accent')] for v in ('piku','piko'))
            policy={'schema_version':1,'target':'hi-piku-piko-v2','accepted_names':['piku','piko'],
                'model_sha256':module.sha(model),'rolling':3,'threshold':.9,
                'frontend':{'sample_rate':16000,'feature_bins':40,'window_ms':30,'feature_step_ms':10,'inference_step_ms':30},
                'frontend_fingerprint':frontend_fingerprint(),'development_passed':True,
                'candidate_frozen_at':'fixture','required_test_cohorts':groups}
            policy_path=root/'wake-policy.json';policy_path.write_text(json.dumps(policy))
            firmware={'model_sha256':module.sha(model),'policy_sha256':module.sha(policy_path),
                'firmware_version':'0.2.2-fixture','app_sha256':'c'*64,'offline_qualified':True}
            report={'status':'mixed-independent-TEST-completed','model_sha256':firmware['model_sha256'],
                'policy_sha256':firmware['policy_sha256'],'protocol_sha256':'d'*64,'manifest_sha256':'e'*64,
                'fixed_policy':{'rolling':3,'threshold':.9},'cases':150,'real_child_TEST_cases':40,
                'family_TEST_only':True,'model_or_policy_selected_using_TEST':False,
                'metrics':{'rolling':3,'threshold':.9,'passed':True,'false_wakes':0,'early_wakes':0,
                    'latency_p95_ms':100,'groups':{g:{'targets':20,'hits':18} for g in groups}}}
            path=root/'report.json';path.write_text(json.dumps(report))
            marker={'status':'completed-consumed','report_sha256':module.sha(path),
                **{k:report[k] for k in ['model_sha256','policy_sha256','protocol_sha256','manifest_sha256']}}
            marker_path=root/'independent-TEST-consumption.json';marker_path.write_text(json.dumps(marker))
            config=module.trial_configuration(firmware,model,policy_path,path)
            self.assertEqual(config['wake_phrase'],'Hi, Pikoo');self.assertEqual(config['pronunciation'],'piku or piko')
            for change in ({'offline_qualified':False},{'offline_qualified':None},{'model_sha256':'wrong'},{'policy_sha256':'wrong'}):
                with self.subTest(change=change),self.assertRaises(ValueError):
                    module.trial_configuration({**firmware,**change},model,policy_path,path)
            for change in ({'cases':70},{'real_child_TEST_cases':0},{'model_or_policy_selected_using_TEST':True}):
                path.write_text(json.dumps({**report,**change}))
                with self.subTest(change=change),self.assertRaises(ValueError):
                    module.trial_configuration(firmware,model,policy_path,path)
            path.write_text(json.dumps(report));marker_path.unlink()
            with self.assertRaises(ValueError):module.trial_configuration(firmware,model,policy_path,path)
            with self.assertRaises(ValueError):module.trial_configuration(firmware,None,None,None)
            legacy=module.trial_configuration(firmware,None,None,None,diagnostic=True)
            self.assertFalse(legacy['runtime_identity_required'])

    def run_fixture(self,tester='adult-1',session=1,start=100,hits=18):
        raw={'status':'real-person-trials-complete','cleanup_verified':True,'diagnostic_only':False,
            'offline_qualified':True,'runtime_identity_verified':True,'tester_id':tester,
            'cloud_sessions_disabled_during_trials':True,
            'tester_role_user_selected':tester.split('-')[0],'session_index':session,
            'model_sha256':'a'*64,'policy_sha256':'b'*64,'app_sha256':'c'*64,
            'sealed_test_report_sha256':'d'*64,
            'started_at_unix':start,'finished_at_unix':start+10,'trials':rows(hits),
            'observer_confirmed':False}
        observation={'report_sha256':hashlib.sha256(json.dumps(raw,sort_keys=True).encode()).hexdigest(),'tester_id':tester,'session_index':session,
            'human_statement':'Fixture observation: all20 targets spoken independently once',
            'observed_at_unix':start+11,'all20_independent_complete_targets_once':True,
            'no_adult_follow_or_repeated_calls':True,'distance_m':1}
        return raw,observation

    def test_observer_evidence_is_post_run_and_cannot_change_machine_trials(self):
        raw,observation=self.run_fixture();old=copy.deepcopy(raw)
        confirmed=module.confirm_observation(raw,observation,observation['report_sha256'])
        self.assertTrue(confirmed['summary']['met_target']);self.assertEqual(raw,old)
        self.assertEqual(confirmed['trials'],raw['trials'])
        self.assertFalse(confirmed['formal_family_acceptance_passed'])
        for change in ({'observed_at_unix':99},{'report_sha256':'wrong'},{'tester_id':'child-1'}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                module.confirm_observation(raw,{**observation,**change},observation['report_sha256'])
        for change in ({'distance_m':.5},{'all20_independent_complete_targets_once':False}):
            self.assertFalse(module.confirm_observation(raw,{**observation,**change},observation['report_sha256'])['summary']['met_target'])

    def test_family_needs_eight_nonoverlapping_verified_person_sessions(self):
        reports=[]
        for i,(tester,session) in enumerate((p,s) for p in ['adult-1','adult-2','child-1','child-2'] for s in [1,2]):
            raw,observed=self.run_fixture(tester,session,100+i*100)
            reports.append(module.confirm_observation(raw,observed,observed['report_sha256']))
        result=module.family_summary(reports)
        self.assertTrue(result['family_two_session_passed']);self.assertFalse(result['formal_goal_completed'])
        with self.assertRaises(ValueError):module.family_summary(reports[:-1])
        with self.assertRaises(ValueError):module.family_summary(reports[:-1]+[reports[0]])
        changed=copy.deepcopy(reports);changed[0]['model_sha256']='d'*64
        with self.assertRaises(ValueError):module.family_summary(changed)
        changed=copy.deepcopy(reports);changed[1]['started_at_unix']=105
        with self.assertRaises(ValueError):module.family_summary(changed)
        changed=copy.deepcopy(reports);changed[0]['trials']=rows(17)
        self.assertFalse(module.family_summary(changed)['family_two_session_passed'])
        changed=copy.deepcopy(reports);changed[1]['raw_run_report_sha256']=changed[0]['raw_run_report_sha256']
        with self.assertRaises(ValueError):module.family_summary(changed)


if __name__ == '__main__':
    unittest.main()
