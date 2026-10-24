"""Keep ignored interior supervision steps in streaming calibration.

An uncertainty mask may contain zeros inside a recording. Those steps still
carry real features and affect subsequent state; only right padding is absent.
This helper cannot infer a speech/phonetic endpoint or change any target label.
"""
import numpy as np


def valid_steps(weights):
    weights = np.asarray(weights)
    if weights.ndim != 1 or not np.isfinite(weights).all() or np.any(weights < 0):
        raise ValueError('Expected a finite nonnegative one-dimensional mask')
    positions = np.flatnonzero(weights > 0)
    if not len(positions):
        raise ValueError('Calibration requires valid recording steps')
    return int(positions[-1]) + 1
