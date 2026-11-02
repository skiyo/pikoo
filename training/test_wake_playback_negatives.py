# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

try:
    import numpy as np
    from wake_playback_negatives import esc_partition, load_rows, metrics, contains_target
    from wake_negative_finetune import windows, recall_preserved, hard_training_sources
    from wake_negative_recalibrate import calibration_sources
except ImportError:
    np = None


@unittest.skipIf(np is None, 'Optional pinned training runtime required')
class PlaybackNegativeIsolation(unittest.TestCase):
    def test_quantization_calibration_excludes_development_and_covers_sources(self):
        rows = [{'source': source, 'split': split, 'sha256': f'{source}:{i}'}
                for source in ('ChildMandarin', 'LibriSpeech-train.100', 'ESC-50')
                for split in ('train', 'validation') for i in range(30)]
        selected = calibration_sources(rows)
        self.assertEqual(len(selected), 40)
        self.assertEqual({r['split'] for r in selected}, {'train'})
        self.assertEqual({r['source'] for r in selected}, {'ChildMandarin', 'LibriSpeech-train.100', 'ESC-50'})
    def test_development_errors_never_become_mined_training_sources(self):
        report = {'cases': [{'split': 'train', 'peak': .4, 'sha256': 'hard-train'},
                            {'split': 'validation', 'peak': 1., 'sha256': 'dev'},
                            {'split': 'train', 'peak': .1, 'sha256': 'easy-train'}]}
        self.assertEqual(hard_training_sources(report), {'hard-train'})
    def test_target_is_excluded_from_ordinary_speech_negatives(self):
        for text in ['Hi, Pikoo!', 'HI PIKO', '嗨，皮库', 'Hi Pee Koo']:
            self.assertTrue(contains_target(text), text)
        self.assertFalse(contains_target('The children are playing outside'))
        self.assertFalse(contains_target('Hi Tikoo'))
    def test_source_folds_stay_separate_and_test_is_unopened(self):
        rows = [{'category': 'door', 'filename': f'{fold}-{i}.wav', 'fold': str(fold),
                 'src_file': f'{fold}:{i}'} for fold in range(1, 6) for i in range(8)]
        selected = esc_partition(rows)
        self.assertEqual(len(selected), 8)
        self.assertFalse(any(r['fold'] == '5' for r in selected))
        self.assertTrue(all(r['fold'] == '4' for r in selected if r['split'] == 'validation'))
        # A corrupt external fold table must not silently introduce leakage.
        rows = [{**r, 'src_file': 'same'} for r in rows]
        with self.assertRaises(ValueError):
            esc_partition(rows)

    def test_crops_cover_the_entire_recording_and_preserve_order(self):
        pcm = np.arange(80123)
        result = windows(pcm)
        covered = np.zeros(len(pcm), bool)
        for offset, piece in result:
            covered[offset:offset+len(piece)] = True
            np.testing.assert_array_equal(piece, pcm[offset:offset+len(piece)])
        self.assertTrue(covered.all())
        self.assertEqual(result[-1][0]+len(result[-1][1]), len(pcm))

    def test_sustained_score_is_not_counted_as_one_event_per_frame(self):
        got = metrics([0]*10+[1]*250)
        self.assertEqual(got['false_events_3s_cooldown'], 3)
        self.assertGreaterEqual(got['first_false_ms'], 300)
        self.assertEqual(metrics([1, 0, 0]*20)['false_events_3s_cooldown'], 0)
        self.assertEqual(metrics([np.float32(.9)]*5, rolling=5)['false_events_3s_cooldown'], 1)

    def test_quiet_model_cannot_pass_recognition_preservation(self):
        original = {'groups': {'child': {'targets': 20, 'hits': 18}},
                    'false_wakes': 0, 'early_wakes': 0}
        self.assertTrue(recall_preserved(original, original))
        quiet = {**original, 'groups': {'child': {'targets': 20, 'hits': 0}}}
        self.assertFalse(recall_preserved(original, quiet))

    def test_protected_and_test_data_fail_before_audio_decoding(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            audio = root/'sample.wav'
            audio.write_bytes(b'not decoded during guard')
            digest = hashlib.sha256(audio.read_bytes()).hexdigest()
            protected, manifest = root/'protected.json', root/'manifest.json'
            row = {'path': audio.name, 'sha256': digest, 'original_sha256': 'source',
                   'source': 'ESC-50', 'source_recording': '1', 'split': 'train',
                   'label': 0, 'household': False}
            manifest.write_text(json.dumps([row]))
            protected.write_text(json.dumps({'audio_sha256': {'frozen': digest}}))
            with self.assertRaises(ValueError):
                load_rows(manifest, protected)
            protected.write_text(json.dumps({'audio_sha256': {}}))
            for change in [{'split': 'test'}, {'household': True}, {'path': '../outside.wav'}]:
                manifest.write_text(json.dumps([{**row, **change}]))
                with self.assertRaises(ValueError):
                    load_rows(manifest, protected)
            manifest.write_text(json.dumps([row, {**row, 'sha256': digest,
                'parent_sha256s': ['protected-parent']}]))
            protected.write_text(json.dumps({'audio_sha256': {'family': 'protected-parent'}}))
            with self.assertRaises(ValueError):
                load_rows(manifest, protected)


if __name__ == '__main__':
    unittest.main()
