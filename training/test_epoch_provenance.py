import json,tempfile,unittest
from pathlib import Path
from epoch_provenance import record,resolve


class EpochProvenanceTest(unittest.TestCase):
    def fixture(self,run):
        (run/'epochs').mkdir()
        (run/'report.json').write_text(json.dumps({'epochs':2,'export_only':False}))
        (run/'training-history.json').write_text(json.dumps({'loss':[1.,.5]}))
        for n in [1,2]:(run/f'epochs/epoch-{n:02}.weights.h5').write_bytes(bytes([n]))

    def test_checkpoint_and_parent_hashes_are_required_and_index_is_idempotent(self):
        with tempfile.TemporaryDirectory() as name:
            run=Path(name);self.fixture(run);proof=record(run)
            self.assertEqual(record(run),proof)
            report,entry=resolve(run/'epochs/epoch-02.weights.h5')
            self.assertEqual(report,run/'report.json');self.assertEqual(entry['epoch'],2)
            (run/'epochs/epoch-02.weights.h5').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'hash'):resolve(run/'epochs/epoch-02.weights.h5')
            with self.assertRaisesRegex(ValueError,'changed'):record(run)

    def test_incomplete_or_mutated_run_fails_closed(self):
        with tempfile.TemporaryDirectory() as name:
            run=Path(name);self.fixture(run);(run/'epochs/epoch-01.weights.h5').unlink()
            with self.assertRaisesRegex(ValueError,'Missing'):record(run)
            (run/'epochs/epoch-01.weights.h5').write_bytes(b'one');record(run)
            (run/'training-history.json').write_text(json.dumps({'loss':[2.,1.]}))
            with self.assertRaisesRegex(ValueError,'metadata'):resolve(run/'epochs/epoch-02.weights.h5')
