"""Causal agreement between two streaming KWS networks, no clip-maximum voting."""
from collections import deque


class Agreement:
    def __init__(self, threshold=.8, rolling=5, coincidence=10,secondary_threshold=None):
        secondary_threshold=threshold if secondary_threshold is None else secondary_threshold
        if not 0<threshold<1 or not 0<secondary_threshold<1 or rolling!=5 or coincidence!=10:
            raise ValueError('Declare both cutoffs with rolling5 and past-only10 agreement')
        self.threshold=threshold
        self.secondary_threshold=secondary_threshold
        self.probabilities=[deque(maxlen=rolling),deque(maxlen=rolling)]
        self.recent=[deque(maxlen=coincidence),deque(maxlen=coincidence)]
    def step(self,a,b):
        for i,p in enumerate([a,b]):
            if not 0<=p<=1:raise ValueError('Invalid probability')
            self.probabilities[i].append(p)
        if len(self.probabilities[0])<5:return 0.
        for i in range(2):self.recent[i].append(sum(self.probabilities[i])/5)
        # Scale only the final decision score: each model's rolling average
        # still uses its original probabilities and explicitly declared cutoff.
        return min(max(self.recent[0]),max(self.recent[1])*(self.threshold/self.secondary_threshold))
