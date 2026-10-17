import importlib.util
from pathlib import Path
import tempfile
import unittest
import wave

@unittest.skipUnless(importlib.util.find_spec('parselmouth'),'Optional Praat augmentation runtime')
class LevelToneTest(unittest.TestCase):
    def test_levelled_tail_preserves_duration_and_leading_pitch(self):
        import numpy as np
        import parselmouth
        from prepare_level_tones import level
        def vowel(a,b):
            f=np.linspace(a,b,4800);phase=2*np.pi*np.cumsum(f)/16000
            return .2*np.sin(phase)+.07*np.sin(2*phase)
        x=np.concatenate([np.zeros(1600),vowel(180,180),np.zeros(1600),vowel(200,290),np.zeros(1600),vowel(320,170),np.zeros(1600)])
        with tempfile.TemporaryDirectory() as tmp:
            source,target=Path(tmp)/'source.wav',Path(tmp)/'target.wav'
            with wave.open(str(source),'wb') as w:w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes((x*32767).astype('<i2').tobytes())
            meta=level(source,target)
            a,b=parselmouth.Sound(str(source)),parselmouth.Sound(str(target))
            self.assertLess(abs(a.duration-b.duration),.002)
            pitch=b.to_pitch(time_step=.01,pitch_floor=65,pitch_ceiling=650);f=pitch.selected_array['frequency'];t=pitch.xs()
            head=f[(t>.15)&(t<.3)&(f>0)];tail=f[(t>.85)&(t<1.1)&(f>0)]
            self.assertLess(abs(float(np.median(head))-180),10)
            self.assertLess(abs(float(np.median(tail))-meta['target_hz']),15)
            self.assertLess(float(np.std(tail)),10)

if __name__=='__main__':unittest.main()
