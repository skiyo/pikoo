# SPDX-License-Identifier: Apache-2.0
import unittest
from wake_train_admission import retained_indices, subset_phrase_events


class TrainAdmission(unittest.TestCase):
    def evidence(self):
        return {'method': 'complete-independent-blind-ASR-content-agreement',
                'household_used': False, 'DEV_used': False, 'TEST_opened': False,
                'labels_changed': False, 'accepted_sha256': ['good'], 'quarantined_sha256': ['uncertain']}

    def metadata(self):
        return [{'sha256': sha, 'source': source} for sha, source in [
            ('good', 'OpenAI-Realtime-synthetic'), ('uncertain', 'Qwen3-TTS-hi-piku-synthetic-local'),
            ('uncertain', 'Qwen3-TTS-hi-piku-synthetic-local'), ('ordinary', 'ChildMandarin')]]

    def test_descendants_quarantined_but_public_negatives_and_extra_examples_kept(self):
        keep, meta, proof = retained_indices(self.evidence(), self.metadata(), 6)
        self.assertEqual(keep.tolist(), [0, 3, 4, 5])
        self.assertEqual([r['sha256'] for r in meta], ['good', 'ordinary'])
        self.assertEqual(proof['excluded_original_and_augmented_examples'], 2)

    def test_missing_coverage_or_protected_data_fails_closed(self):
        for field in ('household_used', 'DEV_used', 'TEST_opened', 'labels_changed'):
            e = self.evidence(); e[field] = True
            with self.assertRaises(ValueError): retained_indices(e, self.metadata(), 6)
        for accepted, quarantined in [(['good'], []), (['good'], ['good', 'uncertain']), (['good', 'DEV'], ['uncertain'])]:
            e = self.evidence(); e.update(accepted_sha256=accepted, quarantined_sha256=quarantined)
            with self.assertRaises(ValueError): retained_indices(e, self.metadata(), 6)

    def test_phrase_metadata_uses_same_retained_order(self):
        metadata = self.metadata()
        archive = {'proof': {}, 'records': [dict(r, original_index=i) for i, r in enumerate(metadata)]}
        result = subset_phrase_events(archive, metadata, [0, 3, 4, 5])
        self.assertEqual([r['original_index'] for r in result['records']], [0, 3])
        archive['records'][1]['sha256'] = 'wrong'
        with self.assertRaises(ValueError): subset_phrase_events(archive, metadata, [0, 3])


if __name__ == '__main__': unittest.main()
