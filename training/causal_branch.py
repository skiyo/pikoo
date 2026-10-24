"""A short ordered acoustic correction alongside a frozen phrase encoder.

The branch learns from the frozen stride-three input features, before the
whole-phrase encoder discards local order. This is a neural hypothesis, not
a hand-coded phoneme veto. No household audio or identity input is used.
"""
import numpy as np


def attach(source, frames=600):
    import tensorflow as tf
    from microwakeword.layers.stream import Stream
    from causal_model import sequence_view
    for layer in source.layers:
        layer.trainable = False
    sequence, graph = sequence_view(source, frames)
    early = next(layer.output for layer in sequence.layers
                 if isinstance(layer, tf.keras.layers.Activation) and len(layer.output.shape) == 4)
    head = sequence.get_layer('near_phrase_probability')
    original = tf.keras.layers.Conv2D(14, 1, trainable=False, name='short_context_original_logits')
    logits = original(head.input)
    kernel, bias = head.get_weights()
    original.set_weights([kernel.reshape(1, 1, *kernel.shape), bias])
    net = early
    for i, size in enumerate((5, 9, 13)):
        net = Stream(tf.keras.layers.Identity(), ring_buffer_size_in_time_dim=size-1,
                     use_one_step=False, pad_time_dim='causal', name=f'short_context_buffer_{i}')(net)
        net = tf.keras.layers.DepthwiseConv2D((size, 1), use_bias=False,
                 name=f'short_context_depthwise_{i}')(net)
        net = tf.keras.layers.Conv2D(24, 1, activation='relu6',
                 name=f'short_context_mix_{i}')(net)
    # A learned ordered temporal kernel, rather than flattening the buffer,
    # also supplies its state with a quantizable integer consumer.
    net = Stream(tf.keras.layers.Identity(), ring_buffer_size_in_time_dim=19,
                 use_one_step=False, pad_time_dim='causal', name='short_context_recent_buffer')(net)
    net = tf.keras.layers.DepthwiseConv2D((20, 1), activation='relu6',
              name='short_context_ordered_ending')(net)
    net = tf.keras.layers.Concatenate(name='short_context_and_phrase')([head.input, net])
    net = tf.keras.layers.Conv2D(32, 1, activation='relu6', name='short_context_hidden')(net)
    net = tf.keras.layers.Dropout(.1, name='short_context_dropout')(net)
    correction = tf.keras.layers.Conv2D(14, 1, kernel_initializer='zeros', bias_initializer='zeros',
        kernel_regularizer=tf.keras.regularizers.l2(1e-4), name='short_context_correction')(net)
    probabilities = tf.keras.layers.Softmax(name='short_context_probability')(
        tf.keras.layers.Add(name='short_context_corrected_logits')([logits, correction]))
    output = tf.keras.layers.Reshape((-1, 14), name='short_context_classes')(probabilities)
    model = tf.keras.Model(sequence.inputs[0], output)
    graph.update(architecture='short-context-24x3-recent20-hidden32',
        short_context={'kernels': [5, 9, 13], 'channels': 24, 'ordered_steps': 20,
                       'hidden_units': 32, 'activation': 'relu6',
                       'original_encoder_and_logits_frozen': True,
                       'trainable_parameters': int(sum(np.prod(v.shape) for v in model.trainable_weights))})
    return model, graph


def integer_anchor(model):
    """Export identity: keep shared phrase-pooling state fully quantized.

    TF 2.18 otherwise retains this recurrent state as float when its pooled
    features feed both the original logits and the new concatenation. A unit
    depthwise consumer is the same proven technique as phonetic_readout.
    """
    import tensorflow as tf
    from microwakeword.layers.stream import Stream
    pool = next(layer for layer in model.layers if isinstance(layer, tf.keras.layers.AveragePooling2D))
    buffer = pool.input._keras_history.operation
    if not isinstance(buffer, Stream) or not isinstance(buffer.cell, tf.keras.layers.Identity):
        raise ValueError('Expected the original phrase-pooling identity buffer')
    name = 'short_context_phrase_integer_anchor'
    if any(layer.name == name for layer in model.layers):
        raise ValueError('Integer anchor already present')

    def call(layer, *args, **kwargs):
        output = layer(*args, **kwargs)
        if layer.name == buffer.name:
            output = tf.keras.layers.DepthwiseConv2D((1, 1), use_bias=False, trainable=False,
                     depthwise_initializer='ones', name=name)(output)
        return output

    anchored = tf.keras.models.clone_model(model, call_function=call)
    original = {layer.name: layer for layer in model.layers}
    for layer in anchored.layers:
        if layer.name == name or isinstance(layer, tf.keras.layers.InputLayer):
            continue
        layer.set_weights(original[layer.name].get_weights())
    return anchored
