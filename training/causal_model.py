"""Expose every causal MixedNet prediction for TRAIN supervision.

This adapter does not change the inference receptive field. It preserves the
source pooling horizon and copies every source weight. Callers must prove
all-step parity with the original streaming graph before fitting a candidate.
It intentionally accepts only the project's simple, single-kernel MixedNet.
"""
import numpy as np


def sequence_view(source, frames):
    import tensorflow as tf
    from microwakeword.layers.stream import Stream

    if not isinstance(frames, int) or frames < 3 or frames % 3:
        raise ValueError('Causal TRAIN length must be a positive multiple of three')
    if len(source.inputs) != 1 or len(source.output.shape) != 2:
        raise ValueError('Expected one original whole-window class model')
    if source.output.shape[-1] != 14:
        raise ValueError('Expected the complete fourteen-class readout')
    flatten = [layer for layer in source.layers if isinstance(layer, tf.keras.layers.Flatten)]
    pools = [layer for layer in source.layers if isinstance(layer, tf.keras.layers.AveragePooling2D)]
    if len(flatten) != 1 or len(pools) != 1:
        raise ValueError('Expected one pre-head Flatten and one temporal average pool')
    if flatten[0].input.shape[1:3] != (1, 1):
        raise ValueError('Only pooled pointwise readouts can become causal')
    if any(type(layer).__name__ in {'StridedDrop', 'StridedKeep', 'ChannelSplit'}
           for layer in source.layers):
        raise ValueError('Multi-kernel or residual time alignment is unsupported')
    if any(isinstance(layer, tf.keras.layers.Reshape) for layer in source.layers):
        raise ValueError('Supply the full class model, not the cropped scalar view')

    def clone(layer):
        config = layer.get_config()
        if isinstance(layer, Stream):
            config['pad_time_dim'] = 'causal'
        elif isinstance(layer, tf.keras.layers.AveragePooling2D):
            config['strides'] = (1, 1)
        elif isinstance(layer, tf.keras.layers.Flatten):
            return tf.keras.layers.Identity(name=layer.name, trainable=layer.trainable)
        return layer.__class__.from_config(config)

    inputs = tf.keras.Input((frames, 40), name='causal_features')
    model = tf.keras.models.clone_model(source, input_tensors=inputs, clone_function=clone)
    copied = []
    for layer in source.layers:
        if layer.get_weights():
            target = model.get_layer(layer.name)
            target.set_weights(layer.get_weights())
            copied.append(layer.name)
    expected = frames // 3
    if tuple(model.output.shape[1:]) != (expected, 1, 14):
        raise ValueError('Causal graph has unexpected time alignment: ' + str(model.output.shape))
    output = tf.keras.layers.Reshape((-1, 14), name='causal_class_sequence')(model.output)
    return tf.keras.Model(inputs, output), {
        'input_frames': frames,
        'output_steps': expected,
        'step_features': 3,
        'source_pool_steps': int(pools[0].pool_size[0]),
        'copied_weight_layers': copied,
        'inference_horizon_changed': False,
    }


def scalar_view(sequence):
    """Select wake class using existing portable reshape/slice operations."""
    import tensorflow as tf
    output = tf.keras.layers.Reshape((-1, 14, 1), name='causal_class_grid')(sequence.output)
    output = tf.keras.layers.Cropping2D(((0, 0), (1, 12)), name='causal_wake_crop')(output)
    output = tf.keras.layers.Flatten(name='causal_wake_sequence')(output)
    return tf.keras.Model(sequence.inputs[0], output)


def streaming(model):
    """Clone a fresh zero-state graph without mutating the caller's TRAIN mode."""
    import tensorflow as tf
    from microwakeword.layers import modes
    from microwakeword.utils import to_streaming_inference
    copy = tf.keras.models.clone_model(model)
    copy.set_weights(model.get_weights())
    config = {'spectrogram_length': int(model.input.shape[1]),
              'feature_bin_count': 40, 'stride': 3}
    return to_streaming_inference(copy, config, modes.Modes.STREAM_INTERNAL_STATE_INFERENCE)


def replay(model, features):
    """Run an entire sequence including cold initial states, never a warmup mask."""
    features = np.asarray(features, np.float32)
    if features.ndim != 2 or features.shape[1] != 40 or len(features) % 3:
        raise ValueError('Expected complete three-feature steps')
    result = [np.asarray(model(features[None, i:i+3], training=False)).reshape(-1)
              for i in range(0, len(features), 3)]
    return np.asarray(result)
