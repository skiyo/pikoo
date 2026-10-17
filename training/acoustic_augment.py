"""Synthetic microphone/room variation for training only; no recorded room audio."""
import numpy as np


def bandlimit(pcm, highpass, lowpass, rate=16000):
    x = np.asarray(pcm, dtype=np.float64)
    if not len(x):
        return x.copy()
    size = 1 << (len(x) + 1023).bit_length()
    padded = np.pad(x, (512, size - len(x) - 512))
    frequency = np.fft.rfftfreq(size, 1 / rate)
    response = 1 / np.sqrt(1 + (frequency / lowpass) ** 8)
    response *= 1 / np.sqrt(1 + (highpass / np.maximum(frequency, 1)) ** 4)
    response[0] = 0
    result = np.fft.irfft(np.fft.rfft(padded) * response, n=size)
    return result[512:512 + len(x)]


def augment(pcm, rng):
    x = np.asarray(pcm, dtype=np.float64).copy()
    if rng.random() < .7:
        x = bandlimit(x, rng.uniform(60, 350), rng.uniform(2600, 7200))
    if len(x) > 640 and rng.random() < .65:
        reverberant = x.copy()
        for _ in range(int(rng.integers(2, 6))):
            delay = int(rng.uniform(.01, min(.18, (len(x) - 1) / 16000)) * 16000)
            reverberant[delay:] += x[:-delay] * rng.uniform(-.2, .3)
        x = reverberant
    # Log-uniform, including soft/distant speech. Does not change speaker IDs.
    return x * 10 ** (rng.uniform(-28, 2) / 20)
