# SPDX-License-Identifier: Apache-2.0
import unittest
import hashlib
import json
from pathlib import Path
import tempfile
from contextlib import ExitStack
from unittest.mock import patch
import numpy as np
from wake_extra_train import append, complete_base_metadata, natural_example


class ExtraTrainMetadata(unittest.TestCase):
    def test_late_append_preserves_prior_arrays_evidence_and_rejects_duplicate_originals(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as mocks:
            root = Path(folder)
            def write(name, body):
                path = root/name; path.write_text(json.dumps(body)); return path
            base = write('base.json', [{'speaker': 'base', 'split': 'train', 'sha256': 'base'}])
            review = write('review.json', {'records': []})
            protected = write('protected.json', {'audio_sha256': {}})
            row = {'sha256': 'new', 'source': 'Qwen3-TTS-hi-piku-synthetic-local', 'label': 1}
            manifest = write('extra.json', [row])
            mocks.enter_context(patch('wake_extra_train.validate', return_value=root/'fixture.wav'))
            mocks.enter_context(patch('wake_extra_train.load_context', return_value=None))
            mocks.enter_context(patch('wake_extra_train.load_natural_context', return_value=None))
            mocks.enter_context(patch('wake_extra_train.validate_natural_row'))
            mocks.enter_context(patch('wake_extra_train.read_audio', return_value=np.zeros(16000)))
            x = np.zeros((1, 6, 40), np.float32)
            y = np.zeros((1, 2), np.float32); w = np.ones_like(y)
            old = {'sha256': 'earlier', 'label': 0, 'sha256_domain': 'original-source-audio'}
            prior = {'manifest_sha256': 'earlier-manifest', 'metadata_sha256': 'earlier-metadata'}
            events = {'records': [old], 'proof': {'extra_audited_TRAIN': prior, 'tempo': 'fixed'}}
            def example(pcm, item, rng, repeat):
                return x[0].copy(), y[0].copy(), w[0].copy(), {'sha256': item['sha256'], 'label': item['label']}
            builder = mocks.enter_context(patch('wake_extra_train.natural_example', side_effect=example))
            args = (x, y, w, [old], events, ['legacy-negative'], manifest, review, base,
                    hashlib.sha256(base.read_bytes()).hexdigest(), protected, root)
            result = append(*args, natural_only=True)
            for actual, original in zip(result[:3], (x, y, w)):
                np.testing.assert_array_equal(actual[:1], original)
                self.assertEqual(len(actual), 13)
            self.assertEqual(builder.call_count, 12)
            self.assertEqual(result[-1]['prior_extra_stages'], [prior])
            self.assertEqual(result[4]['proof']['tempo'], 'fixed')
            self.assertEqual(events['records'], [old])
            self.assertEqual(events['proof']['extra_audited_TRAIN'], prior)
            manifest.write_text(json.dumps([{**row, 'sha256': 'earlier'}]))
            with self.assertRaisesRegex(ValueError, 'earlier extra'):
                append(*args, natural_only=True)
            manifest.write_text(json.dumps([{**row, 'source': 'OpenAI-Realtime-synthetic'}]))
            with self.assertRaisesRegex(ValueError, 'only human-reviewed natural'):
                append(*args, natural_only=True)

    def test_natural_new_original_never_uses_legacy_resampling_and_keeps_clean_clock(self):
        pcm = 5000*np.sin(2*np.pi*440*np.arange(32000)/16000).astype(np.float32)
        original = pcm.copy()
        with patch('wake_extra_train.example', return_value='fixture') as builder:
            self.assertEqual(natural_example(pcm, {}, np.random.default_rng(42), 0), 'fixture')
            args, kwargs = builder.call_args
            np.testing.assert_array_equal(args[0], pcm)
            self.assertEqual(kwargs, {'augment': False})
            self.assertEqual(natural_example(pcm, {}, np.random.default_rng(42), 1), 'fixture')
            args, kwargs = builder.call_args
            self.assertIs(kwargs['augment'], False)
            np.testing.assert_array_equal(kwargs['timing_reference'], pcm)
            self.assertEqual(args[0].shape, pcm.shape)
            middle = args[0][1600:-1600]
            frequencies = np.fft.rfftfreq(len(middle), 1/16000)
            peak = frequencies[np.argmax(abs(np.fft.rfft(middle*np.hanning(len(middle)))))]
            self.assertLess(abs(peak-440), 3)
        np.testing.assert_array_equal(pcm, original)

    def test_preserves_original_metadata_and_types_ordinary_feature_digests(self):
        x = np.zeros((3, 6, 40), np.float32)
        y = np.zeros((3, 2), np.float32); y[0, 1] = 1
        w = np.ones_like(y)
        original = {'sha256': 'original-audio', 'label': 1}
        events = {'proof': {}, 'records': [original]}
        meta, result = complete_base_metadata(x, y, w, [original], events,
                                              ['legacy-positive', 'ChildMandarin', 'public-speech-playlist'])
        self.assertIs(meta[0], original)
        self.assertEqual(len(events['records']), 1)
        self.assertEqual(len(result['records']), 3)
        self.assertEqual(meta[1]['sha256_domain'], 'prepared-TRAIN-feature-example')
        self.assertEqual(meta[2]['contrast_class'], 0)
        self.assertEqual(meta[1]['valid_steps'], 2)
        self.assertFalse(x.any())

    def test_unmapped_positive_or_unknown_source_cannot_be_filled_as_an_ordinary_negative(self):
        x = np.zeros((1, 6, 40), np.float32); y = np.ones((1, 2)); w = np.ones_like(y)
        with self.assertRaises(ValueError): complete_base_metadata(x, y, w, [], {'records': []}, ['ChildMandarin'])
        with self.assertRaises(ValueError): complete_base_metadata(x, y*0, w, [], {'records': []}, ['unknown'])


if __name__ == '__main__': unittest.main()
