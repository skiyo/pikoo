"""TRAIN-only adjacent-speech context; never replace/crop the wake phrase."""
import hashlib
import wave
from pathlib import Path
import numpy as np


class SpeechContext:
    def __init__(self, rows, root, seed=43):
        self.rng = np.random.default_rng(seed)
        self.root = Path(root)
        self.pool = [r for r in rows if r['split'] == 'train' and r['label'] == 0
                     and r.get('source') in {'ChildMandarin', 'PolyAI-MInDS14-zh-CN'}]
        if not self.pool:
            raise ValueError('Speech context requires ordinary-speech TRAIN non-targets')
        if any(r.get('evaluation_only') or r.get('frozen_holdout') or
               str(r.get('source', '')).startswith('private-') for r in rows):
            raise ValueError('Protected evaluation input cannot supply speech context')
        self.background = None

    def prepare(self):
        parts, size = [], 0
        for idx in self.rng.permutation(len(self.pool)):
            row = self.pool[idx]
            path = self.root / row['path']
            if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
                raise ValueError('Speech context recording hash changed')
            with wave.open(str(path)) as stream:
                if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate()) != (1, 2, 16000):
                    raise ValueError('Speech context requires mono PCM16/16kHz')
                pcm = np.frombuffer(stream.readframes(stream.getnframes()), '<i2')
            parts.append(pcm)
            size += len(pcm)
            if size >= 60 * 16000:
                break
        if size < 8 * 16000:
            raise ValueError('At least eight seconds of distinct TRAIN speech is required')
        self.background = np.concatenate(parts).astype(np.float32)

    def apply(self, padded, lead):
        if self.background is None:
            self.prepare()
        # Preserve the target and completion tail exactly. The extra speech
        # warms frontend state before the retained causal training window.
        count = max(lead, 6 * 16000)
        if count > len(self.background):
            raise ValueError('Context is shorter than the requested causal lead')
        start = int(self.rng.integers(0, len(self.background) - count + 1))
        speech = self.background[start:start + count].copy()
        target_rms = max(50., float(np.sqrt(np.mean(padded[lead:] ** 2))))
        speech_rms = max(1., float(np.sqrt(np.mean(speech ** 2))))
        speech *= target_rms / speech_rms * 10 ** (self.rng.uniform(-12, 6) / 20)
        # A random short boundary gap includes both directly adjacent speech
        # and near-adjacent speech. It never overwrites target samples.
        gap = min(lead, int(self.rng.uniform(0, .3) * 16000))
        if gap:
            speech[-gap:] = 0
        return np.concatenate([speech, padded[lead:]])
