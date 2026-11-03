# SPDX-License-Identifier: Apache-2.0
"""Fictional metadata and generated constant PCM; no API, family or inference."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import wave

from wake_mixed_test import COHORTS, protocol, sha, validate_bundle
from wake_mixed_test_labels import assemble
from wake_mixed_test_repair import (
    SLOTS, declaration, generation_rows, repaired_rows, validate_declaration, followup_declaration)
from wake_mixed_test_source import source_plan


class SourceRepair(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.policy = {'target': 'hi-piku-piko-v2', 'development_passed': True,
            'source_native_freeze_sha256': 'native-fixture', 'micro_proof_sha256': 'parity-fixture',
            'required_test_cohorts': COHORTS, 'required_fresh_test_speakers': ['openai:echo', 'openai:shimmer'],
            'model_sha256': 'model-fixture', 'candidate_frozen_at': '2026-11-03T01:00:00+00:00',
            'rolling': 3, 'threshold': .9}
        self.policy_path = self.root / 'wake-policy.json'; self.save(self.policy_path, self.policy)
        self.plan = protocol(self.policy, sha(self.policy_path), 'protection-fixture', '2026-11-03T02:00:00+00:00')
        self.save(self.root/'protocol.json', self.plan)
        self.protocol_sha = sha(self.root/'protocol.json')
        folder = self.root/'synthetic'; folder.mkdir()
        sources = source_plan(self.plan, self.policy, self.protocol_sha)
        self.base = []
        for i, row in enumerate(sources):
            path = folder/(row['request_id']+'.wav'); self.pcm(path, i+1)
            self.base.append({**row, 'status': 'recorded', 'path': path.name,
                'sha256': sha(path), 'created_at': '2026-11-03T03:00:00+00:00'})
        self.save(folder/'manifest.json', self.base)
        self.rejection = self.root/'rejection.json'
        self.save(self.rejection, {'at': '2026-11-03T04:00:00+00:00',
            'all_four_complete_targets_rejected': True,
            'records': [{'id': r['id'], 'sha256': r['sha256']} for r in self.base if r['id'] in SLOTS]})
        pilot_folder = self.root/'pilot'; pilot_folder.mkdir(); self.pilots=[]
        for i, id in enumerate(SLOTS):
            old = next(r for r in self.base if r['id']==id)
            file = pilot_folder/(f'QP{i+1}.wav'); self.pcm(file, i+100)
            self.pilots.append({'request_id': f'QP{i+1}', 'old_TEST_slot': id, 'sha256': sha(file),
                'old_source_sha256': old['sha256'],
                'path': file.name, 'voice': old['voice'], 'style': 'Fixture literal reading.',
                'generation_request_policy': 'literal-target-response-v2',
                'TRAIN_allowed': False, 'wake_model_scored': False, 'synthetic': True,
                'family_inputs_used': False, 'created_at': '2026-11-03T05:00:00+00:00'})
        self.pilot_path = pilot_folder/'manifest.json'; self.save(self.pilot_path, self.pilots)
        slots = {r['id']: r for r in self.plan['slots']}
        self.review = {'reviewed_by': 'human-content-only', 'model_scored': False,
            'human_statement': 'Fictional fixture human observation, not a real audition approval.',
            'reviewed_at': '2026-11-03T06:00:00+00:00', 'records': [
                {'request_id': r['request_id'], 'sha256': r['sha256'],
                 'actual_variant': slots[r['old_TEST_slot']]['prompt'].split()[1],
                 'actual_age': 'adult', 'actual_accent': 'standard', 'quality_valid': True,
                 'complete_hi_and_name': True, 'no_repetition_or_extra_words': True}
                for r in self.pilots]}
        self.review_path = pilot_folder/'human-review.json'; self.save(self.review_path, self.review)
        self.repair = self.declare(); self.repair_path=self.root/'source-repair1-plan.json'
        self.save(self.repair_path, self.repair)

    @staticmethod
    def save(path, value): path.write_text(json.dumps(value))

    @staticmethod
    def pcm(path, value):
        with wave.open(str(path), 'wb') as f:
            f.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
            f.writeframes(value.to_bytes(2, 'little')*2400)

    def declare(self):
        return declaration(self.plan, self.policy_path, self.root, self.rejection,
            self.pilot_path, self.review_path, '2026-11-03T07:00:00+00:00')

    def new_sources(self):
        folder=self.root/'source-repair1';folder.mkdir()
        rows=generation_rows(self.repair,source_plan(self.plan,self.policy,self.protocol_sha),sha(self.repair_path))
        for i,r in enumerate(rows):
            file=folder/(r['request_id']+'.wav');self.pcm(file,i+200)
            r.update(path=file.name,sha256=sha(file),status='recorded',model='gpt-realtime-2.1-mini',
                created_at='2026-11-03T08:00:00+00:00')
        self.save(folder/'manifest.json',rows)
        return rows

    def new_followup(self, existing=False):
        if not existing:self.new_sources()
        prior=repaired_rows(self.plan,self.root,self.policy_path,self.repair_path)
        labels=[]
        for id,row in prior.items():
            bad=id=='TEST-074'
            labels.append({'id':id,'request_id':row['request_id'],'sha256':row['sha256'],
                'model_scored':False,'complete_hi_and_name':not bad,'quality_valid':not bad,
                'actual_label':0 if bad else 1,'heard':'hi-alone' if bad else 'hi-piku-or-piko',
                'actual_age':'adult','actual_accent':'standard','no_repetition_or_extra_words':True,
                'actual_variant':None})
        review={'reviewed_by':'human-content-only','model_scored':False,
            'reviewed_at':'2026-11-03T09:00:00+00:00','human_statement':'Fixture: third only Hi, others normal.',
            'records':labels}
        review_path=self.root/'source-repair1/human-content-feedback.json';self.save(review_path,review)
        value=followup_declaration(self.plan,self.policy_path,self.root,self.repair_path,review_path,
            '2026-11-03T10:00:00+00:00')
        plan_path=self.root/'source-repair2-plan.json';self.save(plan_path,value)
        folder=self.root/'source-repair2';folder.mkdir()
        rows=generation_rows(value,source_plan(self.plan,self.policy,self.protocol_sha),sha(plan_path))
        self.assertEqual(len(rows),1)
        file=folder/(rows[0]['request_id']+'.wav');self.pcm(file,400)
        rows[0].update(path=file.name,sha256=sha(file),status='recorded',model='gpt-realtime-2.1-mini',
            created_at='2026-11-03T11:00:00+00:00')
        self.save(folder/'manifest.json',rows)
        return plan_path,review_path,prior

    def test_declaration_preserves_every_original_and_full_scope(self):
        before={p:sha(p) for p in self.root.rglob('*') if p.is_file()}
        value=self.declare()
        self.assertEqual(value,self.repair)
        self.assertEqual(len(value['requests']),4)
        self.assertEqual(value['whole_TEST_slots'],150)
        self.assertEqual(value['targets_per_actual_cohort'],20)
        self.assertEqual(value['negative_slots'],30)
        self.assertEqual(value['family_slots_still_required'],80)
        self.assertTrue(all(r['request_id']!=r['recipe_audition_id'] for r in value['requests']))
        self.assertEqual(before,{p:sha(p) for p in before})

    def test_missing_partial_or_uncertain_human_recipe_review_never_unlocks(self):
        for change in ({'records':self.review['records'][:-1]}, {'human_statement':''},
                       {'model_scored':True}, {'reviewed_at':'2026-11-03T08:00:00+00:00'}):
            self.save(self.review_path,{**self.review,**change})
            with self.subTest(change=change),self.assertRaises(ValueError):self.declare()
        for change in ({'actual_age':'unknown'},{'actual_accent':'Chinese-accent'},
                       {'actual_variant':'unknown'},{'quality_valid':False},
                       {'complete_hi_and_name':False},{'no_repetition_or_extra_words':False}):
            review=copy.deepcopy(self.review);review['records'][0].update(change);self.save(self.review_path,review)
            with self.subTest(change=change),self.assertRaises(ValueError):self.declare()

    def test_no_consumed_or_sealed_TEST_repair_and_no_scope_changes(self):
        marker=self.root/'independent-TEST-consumption.json';marker.write_text('{}')
        with self.assertRaisesRegex(ValueError,'Consumed'):self.declare()
        marker.unlink();sealed=self.root/'human-review.source-repair1.json'
        self.save(sealed,{'labels_committed_before_model_scores':True})
        with self.assertRaisesRegex(ValueError,'sealed'):self.declare()
        # Reading an already declared plan to score its sealed review is allowed.
        self.assertEqual(validate_declaration(self.repair,self.plan,self.policy_path,self.root),self.repair)
        sealed.unlink()
        for key,value in [('whole_TEST_slots',70),('maximum_attempts_each',2),('automatic_retry',True)]:
            changed={**self.repair,key:value}
            with self.subTest(key=key),self.assertRaises(ValueError):
                validate_declaration(changed,self.plan,self.policy_path,self.root)

    def test_changed_old_attempt_rejection_or_recipe_evidence_is_not_ignored(self):
        for path in (self.rejection,self.pilot_path,self.review_path,self.root/'synthetic/manifest.json'):
            original=path.read_bytes();path.write_bytes(original+b' ')
            with self.subTest(path=path.name),self.assertRaisesRegex(ValueError,'evidence changed'):
                validate_declaration(self.repair,self.plan,self.policy_path,self.root)
            path.write_bytes(original)
        old=next(r for r in self.base if r['id']==SLOTS[0]);(self.root/'synthetic'/old['path']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'original rejected'):self.declare()

    def test_new_originals_assemble_separately_without_deleting_failed_attempts(self):
        original_manifest=sha(self.root/'synthetic/manifest.json');self.new_sources()
        original=assemble(self.plan,self.root)
        amended=assemble(self.plan,self.root,self.repair_path,self.policy_path)
        self.assertEqual(len(amended),150)
        changed=[r['id'] for a,r in zip(original,amended) if a!=r]
        self.assertEqual(changed,list(SLOTS))
        self.assertEqual(sha(self.root/'synthetic/manifest.json'),original_manifest)
        self.assertEqual(sum(r['status']=='missing-not-captured' for r in amended),80)
        self.assertTrue(all(not r['model_scored'] and not r['training_or_tuning_allowed'] for r in amended))
        with self.assertRaisesRegex(ValueError,'explicit pre-score amendment'):
            validate_bundle(self.plan,amended,{},self.root,self.policy,sha(self.policy_path),set(),
                'protection-fixture','manifest-fixture',self.protocol_sha)
        # Even a valid amendment cannot turn missing family/labels into a pass.
        with self.assertRaisesRegex(ValueError,'content review required'):
            validate_bundle(self.plan,amended,{'source_repair_plan_sha256':sha(self.repair_path)},
                self.root,self.policy,sha(self.policy_path),set(),'protection-fixture',
                'manifest-fixture',self.protocol_sha,self.repair_path,self.policy_path)

    def test_pilot_reuse_changed_request_predeclaration_or_missing_attempt_is_rejected(self):
        rows=self.new_sources();folder=self.root/'source-repair1';manifest=folder/'manifest.json'
        for change in ({'status':'failed-source-generation'},{'request_id':'other'},
                       {'created_at':'2026-11-03T06:59:00+00:00'}, {'source_audition':True},
                       {'generation_request_policy':'session-instructions-v1'},{'model_scored':True}):
            changed=copy.deepcopy(rows);changed[0].update(change);self.save(manifest,changed)
            with self.subTest(change=change),self.assertRaises(ValueError):
                repaired_rows(self.plan,self.root,self.policy_path,self.repair_path)
        self.save(manifest,rows[:-1])
        with self.assertRaisesRegex(ValueError,'Exactly four'):repaired_rows(self.plan,self.root,self.policy_path,self.repair_path)
        changed=copy.deepcopy(rows);pilot=self.pilots[0]
        target=folder/changed[0]['path'];target.write_bytes((self.pilot_path.parent/pilot['path']).read_bytes())
        changed[0]['sha256']=sha(target);self.save(manifest,changed)
        with self.assertRaisesRegex(ValueError,'promote auditions'):
            repaired_rows(self.plan,self.root,self.policy_path,self.repair_path)

    def test_same_pilot_PCM_with_a_changed_WAV_header_is_still_protected(self):
        rows=self.new_sources();folder=self.root/'source-repair1';pilot=self.pilots[0]
        target=folder/rows[0]['path']
        raw=(self.pilot_path.parent/pilot['path']).read_bytes()
        # A valid JUNK chunk changes the container hash, not the protected PCM.
        extra=b'JUNK'+(4).to_bytes(4,'little')+b'test'
        changed=raw[:4]+(int.from_bytes(raw[4:8],'little')+len(extra)).to_bytes(4,'little')+raw[8:]+extra
        target.write_bytes(changed);rows[0]['sha256']=sha(target)
        self.save(folder/'manifest.json',rows)
        self.assertNotEqual(rows[0]['sha256'],pilot['sha256'])
        with self.assertRaisesRegex(ValueError,'promote auditions'):
            repaired_rows(self.plan,self.root,self.policy_path,self.repair_path)

    def full_150_fixture(self, followup=False):
        import test_wake_mixed_test as fixtures
        cls=fixtures.MixedTestIsolation;cls.setUpClass()
        try:
            (self.root/'captures').mkdir()
            for slot in self.plan['slots']:
                if slot['source_kind']!='family':continue
                folder=self.root/'captures'/slot['id'];shutil.copytree(cls.root/slot['id'],folder)
                (folder/'TEST.wav').rename(folder/'TEST-only.wav')
                meta=folder/'capture.json';capture=json.loads(meta.read_text())
                capture.update(protocol_sha256=self.protocol_sha,policy_sha256=sha(self.policy_path))
                self.save(meta,capture)
            self.new_sources()
            repair_path=self.new_followup(existing=True)[0] if followup else self.repair_path
            rows=assemble(self.plan,self.root,repair_path,self.policy_path)
            labels=[]
            slots={r['id']:r for r in self.plan['slots']}
            for row in rows:
                slot=slots[row['id']]
                labels.append({'id':row['id'],'sha256':row['sha256'],'quality_valid':True,
                'reviewed_at':'2026-11-03T12:00:00+00:00','actual_label':slot['expected_label'],
                    'actual_age':slot['role'],'actual_accent':slot['accent'],
                    'no_repetition_or_extra_words':True,'complete_hi_and_name':bool(slot['expected_label']),
                    'actual_variant':slot['prompt'].split()[1] if slot['expected_label'] else 'non-target',
                    'completion_ms':50 if slot['expected_label'] else None,
                    'negative_category':slot.get('negative_category')})
            review={'protocol_sha256':self.protocol_sha,'manifest_sha256':'manifest-fixture',
                'model_sha256':self.policy['model_sha256'],'policy_sha256':sha(self.policy_path),
                'labels_committed_before_model_scores':True,'model_scored':False,
                'reviewed_by':'human-content-only','reviewed_at':'2026-11-03T13:00:00+00:00',
                'source_repair_plan_sha256':sha(repair_path),'records':labels}
            self.save(self.root/('human-review.source-repair2.json' if followup else 'human-review.source-repair1.json'),review)
            def validate(value):
                return validate_bundle(self.plan,value,review,self.root,self.policy,sha(self.policy_path),
                    set(),'protection-fixture','manifest-fixture',self.protocol_sha,repair_path,self.policy_path)
            cases=validate(rows)
            self.assertEqual(len(cases),150);self.assertEqual(sum(c['role']=='child' for c in cases),40)
            changed=copy.deepcopy(rows)
            # Source repair must not silently rewrite an unrelated ordinary case.
            next(r for r in changed if r['id']=='TEST-121')['path']='other.wav'
            with self.assertRaisesRegex(ValueError,'exact new original rows'):validate(changed)
            self.assertFalse((self.root/'independent-TEST-consumption.json').exists())
        finally:cls.tearDownClass()

    def test_full_150_fixture_with_sealed_repair_is_valid_but_no_other_source_can_change(self):
        self.full_150_fixture()

    def test_full_150_fixture_with_single_followup_keeps_all_original_coverage(self):
        self.full_150_fixture(followup=True)

    def test_single_followup_keeps_other_three_and_every_failed_original(self):
        path,review,previous=self.new_followup()
        prior_hash=sha(self.root/'source-repair1/manifest.json')
        current=repaired_rows(self.plan,self.root,self.policy_path,path)
        for id in ['TEST-057','TEST-068','TEST-077']:self.assertEqual(current[id],previous[id])
        self.assertNotEqual(current['TEST-074']['sha256'],previous['TEST-074']['sha256'])
        self.assertEqual(current['TEST-074']['old_source_sha256'],previous['TEST-074']['sha256'])
        self.assertEqual(sha(self.root/'source-repair1/manifest.json'),prior_hash)
        self.assertEqual(len(assemble(self.plan,self.root,path,self.policy_path)),150)
        with self.assertRaisesRegex(ValueError,'Only one follow-up'):
            followup_declaration(self.plan,self.policy_path,self.root,path,review,'2026-11-03T14:00:00+00:00')

    def test_single_followup_rejects_changed_human_evidence_extra_rejections_and_old_audio(self):
        path,review,previous=self.new_followup();value=json.loads(path.read_text());original=review.read_bytes()
        for change in ({'model_scored':True},{'human_statement':''},{'reviewed_at':'2026-11-03T07:00:00+00:00'}):
            data=json.loads(original);data.update(change);self.save(review,data)
            with self.subTest(change=change),self.assertRaises(ValueError):
                followup_declaration(self.plan,self.policy_path,self.root,self.repair_path,review,'2026-11-03T10:00:00+00:00')
        data=json.loads(original);data['records'][0]['complete_hi_and_name']=False;self.save(review,data)
        with self.assertRaisesRegex(ValueError,'other three'):
            followup_declaration(self.plan,self.policy_path,self.root,self.repair_path,review,'2026-11-03T10:00:00+00:00')
        review.write_bytes(original)
        changed=copy.deepcopy(value);changed['requests'][0]['voice']='different'
        with self.assertRaisesRegex(ValueError,'follow-up changed'):
            validate_declaration(changed,self.plan,self.policy_path,self.root)
        manifest=self.root/'source-repair2/manifest.json';rows=json.loads(manifest.read_text())
        target=self.root/'source-repair2'/rows[0]['path']
        target.write_bytes((self.root/previous['TEST-074']['path']).read_bytes())
        rows[0]['sha256']=sha(target);self.save(manifest,rows)
        with self.assertRaisesRegex(ValueError,'promote auditions'):
            repaired_rows(self.plan,self.root,self.policy_path,path)


if __name__ == '__main__': unittest.main()
