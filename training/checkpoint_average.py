"""Interpolate compatible floating-point checkpoints before integer export.

This creates one network; it does not run an ensemble on the device. Candidate
selection still requires the complete streaming development gate and untouched
held-out tests. Never mix incompatible tensors or hide a failed checkpoint.
"""
import math
import numpy as np


def interpolate(left,right,right_fraction):
    if not math.isfinite(right_fraction) or not 0<right_fraction<1:
        raise ValueError('Checkpoint fraction must be strictly between 0 and 1')
    if len(left)!=len(right) or not left:raise ValueError('Checkpoint structures differ')
    result=[]
    for a,b in zip(left,right):
        if a.shape!=b.shape or a.dtype!=b.dtype or not np.issubdtype(a.dtype,np.floating):
            raise ValueError('Checkpoint tensor shape or type differs')
        if not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
            raise ValueError('Checkpoint contains non-finite weights')
        # Float64 arithmetic avoids avoidable rounding before the final cast.
        result.append(((1-right_fraction)*a.astype(np.float64)+right_fraction*b.astype(np.float64)).astype(a.dtype))
    return result
