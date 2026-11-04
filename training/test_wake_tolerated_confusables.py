# SPDX-License-Identifier: Apache-2.0
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from wake_tolerated_confusables import POLICY, load, score


class ToleratedConfusables(unittest.TestCase):
    def test_tolerance_never_counts_as_target_recall_or_hides_other_false_wakes(self):
        positive = {'sha256': 'p', 'label': 1, 'cohort': 'adult', 'times_ms': [0, 30, 60, 90],
                    'completion_ms': 30, 'probabilities': [0, 1, 1, 1]}
        t = {**positive, 'sha256': 't', 'label': 0}
        ordinary = {**t, 'sha256': 'ordinary'}
        context = {'originals': {'t': {}}, 'policy_sha256': 'policy'}
        cases = [positive, t]; before = copy.deepcopy(cases)
        metrics, audit = score(cases, context)
        self.assertTrue(metrics['passed'])
        self.assertEqual(metrics['groups']['adult']['targets'], 1)
        self.assertEqual(audit['tolerated_triggered_cases'], 1)
        self.assertEqual(audit['all_cases_retained'], 2)
        self.assertEqual(cases, before)
        self.assertFalse(score([*cases, ordinary], context)[0]['passed'])
        self.assertFalse(score([{**positive, 'probabilities': [0]*4}, t], context)[0]['passed'])
        with self.assertRaises(ValueError): score([{**t, 'label': 1}], context)

    def test_declared_policy_cannot_expand_to_name_only_unknown_or_protected_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            row = {'split': 'validation', 'label': 0, 'text': 'Hi Tikoo', 'sha256': 't',
                   'synthetic': True, 'content_review': 'passed', 'pronunciation_review': 'passed',
                   'target_contract': 'hi-piku-piko-v2'}
            manifest, registry, policy_path = [root/n for n in ('manifest.json','protected.json','policy.json')]
            manifest.write_text(json.dumps([row])); registry.write_text(json.dumps({'audio_sha256': {}}))
            policy = {'revision': POLICY, 'positive_target': 'hi-piku-piko-v2', 'accepted_names': ['piku','piko'],
                      'tolerated_full_phrases': ['Hi Tikoo','Hi Tiko'], 'full_phrase_required': True,
                      'guaranteed_recall_for_tolerated_phrases': False, 'user_confirmed': True,
                      'declared_before_revised_scoring': True, 'tolerated_DEV_source_sha256': ['t']}
            def write():
                policy.update(source_manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                              protected_registry_sha256=hashlib.sha256(registry.read_bytes()).hexdigest())
                policy_path.write_text(json.dumps(policy))
            write(); self.assertEqual(set(load(policy_path,manifest,registry)['originals']), {'t'})
            policy['tolerated_full_phrases'].append('Tikoo'); write()
            with self.assertRaises(ValueError): load(policy_path,manifest,registry)
            policy['tolerated_full_phrases'].pop()
            for key,value in [('text','Tikoo'),('label',1),('family_inputs_used',True),('content_review','pending')]:
                manifest.write_text(json.dumps([{**row,key:value}])); write()
                with self.assertRaises(ValueError): load(policy_path,manifest,registry)
            manifest.write_text(json.dumps([row])); registry.write_text(json.dumps({'audio_sha256': {'test':'t'}})); write()
            with self.assertRaises(ValueError): load(policy_path,manifest,registry)


if __name__ == '__main__': unittest.main()
