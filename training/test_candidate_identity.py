import tempfile
import unittest
from pathlib import Path
from evaluate_candidate import fingerprint, check_fingerprints, new_output


class CandidateIdentityTest(unittest.TestCase):
    def test_candidate_output_cannot_overwrite_an_earlier_run(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'candidate'
            new_output(path)
            (path / 'result.json').write_text('earlier result')
            with self.assertRaises(FileExistsError):
                new_output(path)
            self.assertEqual((path / 'result.json').read_text(), 'earlier result')

    def test_switching_model_or_manifest_after_start_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            files = [Path(directory) / name for name in ('model', 'manifest')]
            for path in files:
                path.write_bytes(b'original')
            snapshot = fingerprint(files)
            check_fingerprints(snapshot)
            for changed in files:
                changed.write_bytes(b'next candidate')
                with self.assertRaisesRegex(ValueError, 'changed'):
                    check_fingerprints(snapshot)
                changed.write_bytes(b'original')


if __name__ == '__main__':
    unittest.main()
