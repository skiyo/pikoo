"""Export-only fusion of two linear logit projections before softmax.

This preserves the learned float function and does not fit, change detector
thresholds or inspect evaluation examples. Integer export otherwise rounds
both potentially cancelling logit vectors before adding them. A single Conv
can accumulate both projections before that output requantization.
"""
import numpy as np


def fuse(model, center=False):
    import tensorflow as tf
    if not isinstance(center, bool):
        raise ValueError('Centering must be explicitly enabled or disabled')
    if len(model.inputs) != 1:
        raise ValueError('Expected one feature input')
    original = model.get_layer('short_context_original_logits')
    correction = model.get_layer('short_context_correction')
    addition = model.get_layer('short_context_corrected_logits')
    probability = model.get_layer('short_context_probability')
    for layer in (original, correction):
        if (not isinstance(layer, tf.keras.layers.Conv2D)
                or layer.kernel_size != (1, 1) or not layer.use_bias
                or tf.keras.activations.serialize(layer.activation) != 'linear'):
            raise ValueError('Fusion requires the two original linear1x1 heads')
    if (not isinstance(addition, tf.keras.layers.Add)
            or list(addition.input) != [original.output, correction.output]
            or probability.input is not addition.output
            or not isinstance(probability, tf.keras.layers.Softmax)
            or original.output.shape != correction.output.shape):
        raise ValueError('Unexpected residual logit graph')
    if any(layer.name.startswith('short_context_fused_') for layer in model.layers):
        raise ValueError('Logit heads already fused')
    left, lb = original.get_weights()
    right, rb = correction.get_weights()
    features = tf.keras.layers.Concatenate(name='short_context_fused_features')(
        [original.input, correction.input])
    head = tf.keras.layers.Conv2D(original.filters, 1, trainable=False,
                                 name='short_context_fused_logits')
    logits = head(features)
    kernel, bias = np.concatenate([left, right], axis=2), lb + rb
    if center:
        # Subtracting the same feature-dependent scalar from every class
        # leaves softmax unchanged. Fold this into weights, with no runtime
        # reduction/subtraction ops or changed target/detection semantics.
        kernel = kernel - kernel.mean(axis=-1, keepdims=True)
        bias = bias - bias.mean()
    head.set_weights([kernel, bias])
    probabilities = tf.keras.layers.Softmax(axis=probability.axis,
                                           name='short_context_fused_probability')(logits)
    classes = tf.keras.layers.Reshape((-1, original.filters),
                                     name='short_context_fused_classes')(probabilities)
    return tf.keras.Model(model.inputs[0], classes)
