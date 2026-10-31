# SPDX-License-Identifier: Apache-2.0
"""Protect one-shot TEST boundaries without accessing any real recordings."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from hi_pikoo_sealed_review import validate_test


class SealedTestBoundaries(unittest.TestCase):
    def test_only_new_candidate_bound_fictional_test_originals_are_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root/'fictional.wav'
            original.write_bytes(b'fixture-not-an-audio-recording')
            digest = hashlib.sha256(original.read_bytes()).hexdigest()
            policy = {'model_sha256': 'frozen-model'}
            row = {'split': 'test', 'evaluation_only': True,
                   'frozen_holdout': True, 'synthetic': True,
                   'source': 'OpenAI-Realtime-synthetic',
                   'frozen_candidate_sha256': 'frozen-model',
                   'path': original.name, 'sha256': digest}
            self.assertEqual(validate_test(row, root, set(), policy), original.resolve())
            for change in ({'split': 'train'}, {'evaluation_only': False},
                           {'frozen_holdout': False}, {'real_child': True},
                           {'family_inputs_used': True}, {'reference_audio_used': True},
                           {'parent_sha256': digest}, {'sha256': 'changed'},
                           {'frozen_candidate_sha256': 'another-model'}):
                with self.subTest(change=change), self.assertRaises(ValueError):
                    validate_test({**row, **change}, root, set(), policy)
            with self.assertRaises(ValueError):
                validate_test(row, root, {digest}, policy)
            with self.assertRaises(ValueError):
                validate_test({**row, 'path': '../fictional.wav'}, root, set(), policy)


if __name__ == '__main__':
    unittest.main()
