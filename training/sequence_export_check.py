"""Compare a trained causal batch view against its saved stateful stream.

Use authorized TRAIN features only. Each replay loads fresh saved states and
checks every step, including cold initial states. This proves a numeric export
contract; it does not establish keyword accuracy or device acceptance.
"""
import numpy as np


def check(network, saved, features, targets, samples=8, tolerance=1e-5):
    import tensorflow as tf
    if samples < 2 or samples % 2 or not 0 < tolerance <= 1e-4:
        raise ValueError('Expected a bounded balanced numeric export check')
    targets = np.asarray(targets, bool)
    if len(features) != len(targets):
        raise ValueError('Feature/target count mismatch')
    chosen = []
    for value in (False, True):
        pool = np.flatnonzero(targets == value)
        if not len(pool):
            raise ValueError('Both TRAIN classes must be represented')
        count = min(samples//2, len(pool))
        chosen.extend(pool[np.linspace(0, len(pool)-1, count).astype(int)].tolist())
    cases = []
    for index in chosen:
        data = np.asarray(features[index], np.float32)
        if data.shape[1:] != (40,) or len(data) % 3:
            raise ValueError('Expected complete three-feature frontend steps')
        expected = np.asarray(network(data[None], training=False)).reshape(-1)
        if len(expected) != len(data)//3:
            raise ValueError('Expected a scalar causal sequence from the trained graph')
        restored = tf.saved_model.load(str(saved))
        serve = restored.signatures['serve']
        actual = []
        for offset in range(0, len(data), 3):
            reply = serve(tf.constant(data[None, offset:offset+3]))
            if len(reply) != 1:
                raise ValueError('Expected one saved streaming probability output')
            probability = np.asarray(next(iter(reply.values())))
            if probability.size != 1:
                raise ValueError('Expected a scalar saved streaming probability')
            actual.append(float(probability.flat[0]))
        error = abs(expected-np.asarray(actual))
        if not np.isfinite(error).all():
            raise ValueError('Nonfinite causal export comparison')
        cases.append({'feature_index': int(index), 'target': bool(targets[index]),
            'steps': len(actual), 'max_absolute_error': float(error.max()),
            'mean_absolute_error': float(error.mean()), 'passed': bool(error.max() <= tolerance)})
    return {'status': 'passed-trained-sequence-export-parity' if all(c['passed'] for c in cases)
            else 'failed-trained-sequence-export-parity', 'tolerance': tolerance, 'cases': cases,
            'scope': 'TRAIN-only batch scalar vs saved stateful scalar, all steps, fresh states per case',
            'accuracy_or_device_acceptance': False}
