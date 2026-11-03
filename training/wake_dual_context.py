# SPDX-License-Identifier: Apache-2.0
"""Opt-in short temporal branch, initialized to preserve a loaded long donor.

No corpus, network or device access. This is a bounded architectural control,
not a new decision rule: export still emits one stateful wake probability.
"""
import numpy as np


def add_short_context(base, steps=20):
    """Add a 20-step ordered branch alongside the existing 72-step branch.

    Load the original checkpoint into ``base`` first. Its encoder/long hidden
    path is shared, not cloned or reinitialized. Zero short-classifier weights
    preserve the donor function initially (subject to floating-point rounding).
    The short feature branch gets gradients after its classifier weights learn.
    """
    if type(steps) is not int or steps != 20:
        raise ValueError('Only the predeclared 20-step short branch is supported')
    import tensorflow as tf
    from microwakeword.layers.stream import Stream
    context = base.get_layer('ordered_context')
    if context.ring_buffer_size_in_time_dim != 71:
        raise ValueError('The short branch requires a 72-step long donor')
    if any(layer.name == 'short_ordered_context' for layer in base.layers):
        raise ValueError('A short branch is already attached')
    head = base.get_layer('wake_probability')
    kernel, bias = head.get_weights()
    if kernel.shape[:2] != (1, 1) or kernel.shape[-1] != 1 or bias.shape != (1,):
        raise ValueError('Expected the original scalar pointwise wake classifier')
    channels = int(context.input.shape[-1])
    units = int(kernel.shape[-2])
    short = Stream(tf.keras.layers.Identity(), ring_buffer_size_in_time_dim=steps-1,
                   use_one_step=False, pad_time_dim='causal',
                   name='short_ordered_context')(context.input)
    short = tf.keras.layers.DepthwiseConv2D((steps, 1), use_bias=False, activation='relu6',
        depthwise_initializer=tf.keras.initializers.RandomNormal(stddev=np.sqrt(2/steps)),
        name='short_ordered_filter')(short)
    short = tf.keras.layers.Conv2D(units, 1, activation='relu6', kernel_initializer='he_normal',
                                  name='short_hidden')(short)
    joint = tf.keras.layers.Concatenate(name='dual_context_features')([head.input, short])
    output = tf.keras.layers.Conv2D(1, 1, activation='sigmoid', name='wake_probability')(joint)
    model = tf.keras.Model(base.input, tf.keras.layers.Reshape((-1,))(output))
    model.get_layer('wake_probability').set_weights(
        [np.concatenate([kernel, np.zeros_like(kernel)], axis=2), bias])
    return model, {'long_context_steps': 72, 'short_context_steps': steps,
                   'shared_encoder_channels': channels, 'hidden_units_per_branch': units,
                   'short_classifier_initially_zero': True,
                   'donor_long_path_weights_shared': True,
                   'parameters_before': base.count_params(), 'parameters_after': model.count_params(),
                   'scalar_streaming_ABI_unchanged': True}
