"""Grow a nonlinear readout without changing the initial pretrained function.

Freeze the proven feature encoder (including batch-normalization statistics),
then learn a small residual correction to its original probability logit.
"""
import tensorflow as tf


def freeze_normalization(model):
    """Keep pretrained running statistics and affine BN parameters unchanged."""
    for layer in model.layers:
        if isinstance(layer,tf.keras.layers.BatchNormalization):layer.trainable=False


def attach(base,units):
    if not isinstance(units,int) or not 16<=units<=256:
        raise ValueError('Residual readout must have 16..256 hidden units')
    if len(base.inputs)!=1:raise ValueError('Expected one audio feature input')
    head=base.layers[-1]
    if not isinstance(head,tf.keras.layers.Dense) or head.units!=1 or head.get_config()['activation']!='sigmoid':
        raise ValueError('Expected one Dense sigmoid probability head')
    for layer in base.layers:layer.trainable=False
    features=head.input
    original=tf.keras.layers.Dense(1,activation=None,trainable=False,name='wake_frozen_logit')
    logit=original(features)
    original.set_weights(head.get_weights())
    hidden=tf.keras.layers.Dense(units,activation='relu',name='wake_readout_hidden')(features)
    hidden=tf.keras.layers.Dropout(.1,name='wake_readout_dropout')(hidden)
    correction=tf.keras.layers.Dense(1,kernel_initializer='zeros',bias_initializer='zeros',
        kernel_regularizer=tf.keras.regularizers.l2(1e-4),name='wake_logit_correction')(hidden)
    output=tf.keras.layers.Activation('sigmoid',name='wake_corrected_probability')(
        tf.keras.layers.Add(name='wake_corrected_logit')([logit,correction]))
    return tf.keras.Model(base.inputs[0],output)
