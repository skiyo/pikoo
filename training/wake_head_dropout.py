# SPDX-License-Identifier: Apache-2.0
"""Opt-in utterance-wise hidden-channel dropout; inference is the loaded donor.

No audio transformation, new data, downloads, device or corpus access.
"""
def add_head_dropout(base, rate=.2, seed=42):
    if type(rate) is not float or rate != .2 or type(seed) is not int or seed not in (42, 43):
        raise ValueError('Only predeclared dropout .2 and seeds42/43 are supported')
    import tensorflow as tf
    if any(x.name in ('short_ordered_context', 'wake_head_dropout') for x in base.layers):
        raise ValueError('This isolated control requires an unchanged single-context donor')
    if base.get_layer('ordered_context').ring_buffer_size_in_time_dim != 71:
        raise ValueError('The control requires a 72-step donor')
    head = base.get_layer('wake_probability')
    kernel, bias = head.get_weights()
    units = int(head.input.shape[-1])
    dropped = tf.keras.layers.Dropout(rate, noise_shape=(None, 1, 1, units), seed=seed,
                                     name='wake_head_dropout')(head.input)
    # A new scalar classifier avoids multiple inbound nodes on the old layer:
    # the auxiliary training head must see the same dropped features too.
    output = tf.keras.layers.Conv2D(1, 1, activation='sigmoid', name='wake_probability')(dropped)
    model = tf.keras.Model(base.input, tf.keras.layers.Reshape((-1,))(output))
    model.get_layer('wake_probability').set_weights([kernel, bias])
    if model.count_params() != base.count_params():
        raise ValueError('Training regularization must not add inference parameters')
    return model, {'classifier_dropout': rate, 'dropout_seed': seed,
                   'dropout_noise_shape': [None, 1, 1, units],
                   'same_channel_mask_across_utterance_time': True,
                   'dropout_identity_at_inference': True,
                   'loaded_classifier_weights_transferred': True,
                   'parameters_before': base.count_params(), 'parameters_after': model.count_params(),
                   'scalar_streaming_ABI_unchanged': True}
