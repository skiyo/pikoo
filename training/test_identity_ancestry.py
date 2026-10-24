import hashlib
import tempfile
import unittest
from pathlib import Path
from repair_identity_ancestry import repair


class IdentityAncestryTest(unittest.TestCase):
    def rows(self, directory):
        data = b'unchanged-public-speech-bytes'
        (directory / 'original.wav').write_bytes(data)
        (directory / 'copy.wav').write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        original = dict(sha256=digest, path='original.wav', label=0, split='train',
                        source='ChildMandarin', group='public-train', text='ordinary speech')
        return [original, {**original, 'path': 'copy.wav', 'parent_sha256': digest,
                           'mined_training_prefix': True}]

    def test_verified_identity_repairs_only_metadata_and_preserves_multiplicity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = self.rows(root)
            fixed, report = repair(rows, root, set())
            self.assertIn('parent_sha256', rows[1])
            self.assertNotIn('parent_sha256', fixed[1])
            self.assertEqual([r['sha256'] for r in fixed], [r['sha256'] for r in rows])
            self.assertEqual([r['label'] for r in fixed], [0, 0])
            self.assertEqual(report['row_occurrences_removed'], 0)
            self.assertEqual(len(report['changes']), 1)

    def test_private_protected_test_or_transformed_sources_cannot_use_the_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = self.rows(root)
            for changes in [{'source': 'Qwen3-TTS-synthetic-local'}, {'label': 1},
                            {'split': 'test'}, {'family_inputs_used': True},
                            {'augmentation': {'method': 'crop'}}]:
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    repair([rows[0], {**rows[1], **changes}], root, set())
            with self.assertRaises(ValueError):
                repair(rows, root, {rows[0]['sha256']})

    def test_missing_original_different_content_and_changed_file_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = self.rows(root)
            with self.assertRaises(ValueError):
                repair(rows[1:], root, set())
            with self.assertRaises(ValueError):
                repair([rows[0], {**rows[1], 'text': 'different words'}], root, set())
            (root / 'copy.wav').write_bytes(b'changed')
            with self.assertRaises(ValueError):
                repair(rows, root, set())

    def test_identity_copy_restores_recorded_upstream_instead_of_dropping_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = self.rows(root)
            rows[0]['parent_sha256'] = 'upstream'
            fixed, report = repair(rows, root, set())
            self.assertEqual(fixed[1]['parent_sha256'], 'upstream')
            self.assertEqual(report['changes'][0]['restored_parents'], ['upstream'])

    def test_alternate_origins_of_identical_bytes_are_unioned_for_all_occurrences(self):
        from corpus_ancestry import parents
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = self.rows(root)
            rows[0]['parent_sha256'] = 'upstream-a'
            rows[1]['parent_sha256'] = 'upstream-b'
            fixed, report = repair(rows, root, set())
            self.assertEqual(parents(fixed[0]), {'upstream-a', 'upstream-b'})
            self.assertEqual(parents(fixed[1]), {'upstream-a', 'upstream-b'})
            self.assertEqual(len(report['alternate_origin_groups']), 1)
            self.assertEqual(len(fixed), 2)
            with self.assertRaises(ValueError):
                repair(fixed, root, {'upstream-b'})


if __name__ == '__main__':
    unittest.main()
