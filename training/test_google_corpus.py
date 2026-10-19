import base64
import importlib.util
import io
import unittest
import wave

AVAILABLE = importlib.util.find_spec('numpy') is not None


@unittest.skipUnless(AVAILABLE, 'Optional synthesis runtime is not installed')
class GoogleCorpusTest(unittest.TestCase):
    def test_level_only_curriculum_retains_splits_and_near_phrase_negatives(self):
        from generate_google import jobs
        original=jobs();rows=jobs(level_contrasts=True)
        self.assertEqual(len(rows),96)
        self.assertEqual({r['speaker']:r['split'] for r in rows},
                         {r['speaker']:r['split'] for r in original})
        self.assertEqual({r['pronunciation'] for r in rows if r['label']},{'mixed-pi1-ku1'})
        for voice in {r['voice'] for r in rows}:
            selected=[r for r in rows if r['voice']==voice]
            self.assertEqual(sum(r['label'] for r in selected),4)
            self.assertEqual(sum('Pikoo' in r['text'] for r in selected),2)
            self.assertEqual({r['text'] for r in selected if not r['label']},
                             {'你好皮克','你好皮球','你好皮','你真酷'})
            self.assertTrue(all(r['synthetic'] and not r['real_child'] for r in selected))

    def test_mixed_targets_preserve_speaker_splits_and_negative_labels(self):
        from generate_google import jobs
        from review_google_corpus import normalize
        rows=jobs(True)
        for split in ('train','validation','test'):
            self.assertTrue(any(r['split']==split and r['label'] and 'Pikoo' in r['text'] for r in rows))
        self.assertEqual({r['pronunciation'] for r in rows if r['label']},{'mandarin-pi2-ku4','mixed-pi1-ku1'})
        self.assertEqual(normalize('你好Pikoo'),normalize('你好批枯'))
        self.assertNotEqual(normalize('你好Pikoo'),normalize('你好'))
        self.assertNotEqual(normalize('你好Pikoo'),normalize('你好屁股'))
        self.assertEqual(normalize('你好Pikoo'),normalize('你好，披哭。'))
        for wrong in ['你好皮狗','你好皮克','你好皮球','你好比酷','你好PQ']:
            self.assertNotEqual(normalize('你好Pikoo'),normalize(wrong))
    def test_synthetic_voice_identities_do_not_cross_splits(self):
        from generate_google import jobs
        rows = jobs()
        self.assertEqual(len(rows), 96)
        groups = {}
        for row in rows:
            self.assertEqual(groups.setdefault(row['speaker'], row['split']), row['split'])
            self.assertTrue(row['synthetic'])
            self.assertFalse(row['real_child'])
        for split in ('train', 'validation', 'test'):
            self.assertEqual({r['label'] for r in rows if r['split'] == split}, {0, 1})

    def test_decode_requires_complete_wav_and_converts_to_16khz(self):
        import numpy as np
        from generate_google import decode_audio
        out = io.BytesIO()
        with wave.open(out, 'wb') as w:
            w.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
            w.writeframes((np.sin(np.arange(24000) * .13) * 5000).astype('<i2').tobytes())
        response = {'status': 'completed', 'steps': [{'type': 'model_output',
            'content': [{'type': 'audio', 'data': base64.b64encode(out.getvalue()).decode()}]}]}
        result = decode_audio(response)
        self.assertEqual(len(result), 16000)
        self.assertGreater(float(np.max(result)), 1000)
        response['status'] = 'in_progress'
        with self.assertRaisesRegex(ValueError, 'complete'):
            decode_audio(response)

    def test_legacy_pcm_decodes_and_incomplete_output_is_rejected(self):
        import numpy as np
        from generate_google import decode_audio
        pcm = (np.sin(np.arange(24000) * .13) * 5000).astype('<i2')
        response = {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [
            {'inlineData': {'mimeType': 'audio/L16;rate=24000',
                            'data': base64.b64encode(pcm.tobytes()).decode()}}]}}]}
        result = decode_audio(response)
        self.assertEqual(len(result), 16000)
        self.assertGreater(float(np.max(result)), 1000)
        response['candidates'][0]['finishReason'] = 'MAX_TOKENS'
        with self.assertRaisesRegex(ValueError, 'complete'):
            decode_audio(response)

    def test_pause_alignment_rejects_missing_or_extra_utterances(self):
        import numpy as np
        from generate_google import split_utterances
        speech = (np.sin(np.arange(8000) * .13) * 5000).astype('<i2')
        pcm = np.concatenate([speech, np.zeros(16000, '<i2'), speech])
        clips = split_utterances(pcm, 2)
        self.assertEqual(len(clips), 2)
        self.assertTrue(all(len(c) >= len(speech) for c in clips))
        with self.assertRaisesRegex(ValueError, 'alignment failed'):
            split_utterances(pcm, 3)

    def test_antialias_filter_suppresses_above_target_nyquist(self):
        import numpy as np
        from generate_google import resample
        time = np.arange(24000) / 24000
        low = resample(np.sin(2 * np.pi * 3000 * time) * 5000, 24000)[100:-100]
        high = resample(np.sin(2 * np.pi * 10000 * time) * 5000, 24000)[100:-100]
        self.assertLess(float(np.mean(high ** 2)), float(np.mean(low ** 2)) * .01)

    def test_telephone_mulaw_extremes_and_silence(self):
        import numpy as np
        import struct
        from import_minds14 import decode_wave
        fmt = struct.pack('<HHIIHH', 7, 1, 8000, 8000, 1, 8)
        data = bytes([255, 127, 0, 128])
        chunks = b'fmt ' + struct.pack('<I', len(fmt)) + fmt + b'data' + struct.pack('<I', len(data)) + data
        blob = b'RIFF' + struct.pack('<I', len(chunks) + 4) + b'WAVE' + chunks
        np.testing.assert_array_equal(decode_wave(blob), [0, 0, -32124, 32124])


if __name__ == '__main__':
    unittest.main()
