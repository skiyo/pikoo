"""Experimental short-context branch for wake-word endings.

The frozen whole-phrase encoder remains intact. A trainable causal branch sees
the last 1.32 seconds with temporal order retained, then corrects the old logit.
This is a trainable acoustic hypothesis, not a hand-coded phoneme detector.
"""
import tensorflow as tf


def attach(base):
    # Imports come from the caller's pinned upstream microWakeWord checkout.
    from microwakeword.mixednet import MixConv
    from microwakeword.layers import stream,strided_drop
    head=base.layers[-1]
    if not isinstance(head,tf.keras.layers.Dense) or head.units!=1 or head.get_config()['activation']!='sigmoid':
        raise ValueError('Expected one Dense sigmoid probability head')
    early=next((layer.output for layer in base.layers
        if isinstance(layer,tf.keras.layers.Activation) and len(layer.output.shape)==4),None)
    if early is None or early.shape[1] is None or early.shape[1]<45:
        raise ValueError('Expected a causal stride-3 feature encoder with sufficient context')
    for layer in base.layers:layer.trainable=False
    net=early
    for n,kernel in enumerate([5,9,13]):
        net=MixConv([kernel])(net)
        net=tf.keras.layers.Conv2D(24,1,use_bias=False,name=f'ending_conv_{n}')(net)
        net=tf.keras.layers.BatchNormalization(name=f'ending_norm_{n}')(net)
        net=tf.keras.layers.Activation('relu',name=f'ending_relu_{n}')(net)
    keep=20
    net=strided_drop.StridedDrop(int(net.shape[1])-keep,name='ending_keep_recent')(net)
    net=stream.Stream(cell=tf.keras.layers.Identity(),ring_buffer_size_in_time_dim=keep-1,
        use_one_step=False,name='ending_recent_buffer')(net)
    net=tf.keras.layers.Flatten(name='ending_ordered_features')(net)
    net=tf.keras.layers.Concatenate(name='ending_and_phrase')([head.input,net])
    net=tf.keras.layers.Dense(64,activation='relu',name='ending_classifier')(net)
    net=tf.keras.layers.Dropout(.1,name='ending_dropout')(net)
    correction=tf.keras.layers.Dense(1,kernel_initializer='zeros',bias_initializer='zeros',
        kernel_regularizer=tf.keras.regularizers.l2(1e-4),name='ending_correction')(net)
    original=tf.keras.layers.Dense(1,trainable=False,name='ending_original_logit')
    logit=original(head.input);original.set_weights(head.get_weights())
    out=tf.keras.layers.Activation('sigmoid',name='ending_probability')(
        tf.keras.layers.Add(name='ending_logit')([logit,correction]))
    return tf.keras.Model(base.inputs[0],out)
