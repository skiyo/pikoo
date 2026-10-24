import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
import shutil
import wave

spec = importlib.util.spec_from_file_location('voice_variants', Path(__file__).with_name('prepare_voice_variants.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class VoiceVariantSafetyTest(unittest.TestCase):
    def test_fast_profiles_are_explicit_and_bounded(self):
        with self.assertRaises(ValueError):module.validate_profiles([(0.,1.6)])
        module.validate_profiles([(0.,1.6)],fast_speech=True)
        for tempo in (float('nan'),float('inf'),2.01,.74):
            with self.assertRaises(ValueError):module.validate_profiles([(0.,tempo)],fast_speech=True)

    def test_fast_mode_rejects_development_before_reading_audio(self):
        with self.assertRaisesRegex(ValueError,'TRAIN-only'):
            module.validate([dict(split='validation')],Path('/unused'),set(),training_only=True)

    @unittest.skipUnless(shutil.which('ffmpeg') and importlib.util.find_spec('numpy'), 'Optional FFmpeg/NumPy runtime')
    def test_fast_transform_shortens_duration_without_raising_pitch(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as tmp:
            source,target=Path(tmp)/'source.wav',Path(tmp)/'target.wav'
            pcm=(8000*np.sin(2*np.pi*220*np.arange(32000)/16000)).astype('<i2')
            with wave.open(str(source),'wb') as audio:
                audio.setparams((1,2,16000,0,'NONE','not compressed'));audio.writeframes(pcm.tobytes())
            module.transform(shutil.which('ffmpeg'),source,target,0.,1.75)
            with wave.open(str(target)) as audio:
                output=np.frombuffer(audio.readframes(audio.getnframes()),'<i2')
            self.assertLess(abs(len(output)/len(pcm)-1/1.75),.05)
            peak=np.argmax(abs(np.fft.rfft(output)))*16000/len(output)
            self.assertLess(abs(peak-220),5)

    @unittest.skipUnless(shutil.which('ffmpeg') and importlib.util.find_spec('numpy'), 'Optional FFmpeg/NumPy runtime')
    def test_pitch_changes_without_forcing_the_speech_to_become_faster(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / 'source.wav', Path(tmp) / 'target.wav'
            pcm = (8000 * np.sin(2 * np.pi * 220 * np.arange(32000) / 16000)).astype('<i2')
            with wave.open(str(source), 'wb') as audio:
                audio.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
                audio.writeframes(pcm.tobytes())
            module.transform(shutil.which('ffmpeg'), source, target, 4, 1.)
            with wave.open(str(target)) as audio:
                output = np.frombuffer(audio.readframes(audio.getnframes()), '<i2')
            self.assertLess(abs(len(output) / len(pcm) - 1), .05)
            peak = np.argmax(abs(np.fft.rfft(output))) * 16000 / len(output)
            self.assertLess(abs(peak - 220 * 2 ** (4 / 12)), 5)

    def test_renamed_household_audio_is_rejected_before_transform(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blob = b'reserved human audio fixture'
            (root / 'renamed.wav').write_bytes(blob)
            digest = hashlib.sha256(blob).hexdigest()
            row = dict(path='renamed.wav', sha256=digest, split='train', label=1,
                       source='Google-Gemini-TTS-synthetic', speaker='synthetic-one')
            with self.assertRaisesRegex(ValueError, 'Protected human recording'):
                module.validate([row], root, {digest})
            row['evaluation_only'] = True
            with self.assertRaisesRegex(ValueError, 'evaluation audio'):
                module.validate([row], root, set())

    def test_test_split_and_cross_split_derivatives_cannot_be_training_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'one.wav').write_bytes(b'one')
            digest = hashlib.sha256(b'one').hexdigest()
            row = dict(path='one.wav', sha256=digest, split='test', label=1, speaker='one')
            with self.assertRaisesRegex(ValueError, 'Test recordings'):
                module.validate([row], root, set())
            row['split'] = 'train'
            with self.assertRaisesRegex(ValueError, 'speaker crosses splits'):
                module.validate([row, {**row, 'split': 'validation'}], root, set())


if __name__ == '__main__':
    unittest.main()
