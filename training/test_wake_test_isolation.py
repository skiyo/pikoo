# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import tempfile
import unittest
from wake_test_isolation import validate, identities, splits, sha


class TestIsolation(unittest.TestCase):
    def test_metadata_only_reservation_rejects_any_used_source_identity_or_manifest_change(self):
        with tempfile.TemporaryDirectory() as folder:
            manifest = Path(folder)/'synthetic.json'
            rows = [{'speaker': 'openai:'+voice, 'split': split, 'source': 'OpenAI-Realtime-synthetic',
                     'synthetic': True, 'real_child': False, 'family_inputs_used': False,
                     'reference_audio_used': False}
                    for voice, split in [('cedar', 'train'), ('ash', 'validation'), ('ballad', 'test')]]
            manifest.write_text(json.dumps(rows))
            evidence = {'target': 'hi-piku-piko-v2', 'declared_at': 'fixture',
                'reserved_source_speakers': ['openai:echo', 'openai:shimmer'],
                'used_source_speakers': identities([manifest]), 'covered_splits': splits([manifest]),
                'metadata_only': True, 'audio_read': False, 'household_used': False,
                'source_manifests_sha256': {str(manifest.resolve()): sha(manifest)}}
            validate(evidence, [manifest])
            with self.assertRaises(ValueError): validate({**evidence, 'used_source_speakers': ['openai:echo']})
            with self.assertRaises(ValueError): validate({**evidence, 'covered_splits': ['train', 'validation']})
            rows[0]['speaker'] = 'openai:shimmer'; manifest.write_text(json.dumps(rows))
            with self.assertRaises(ValueError): validate(evidence, [manifest])
            rows[0]['family_inputs_used'] = True; manifest.write_text(json.dumps(rows))
            with self.assertRaises(ValueError): identities([manifest])


if __name__ == '__main__': unittest.main()
