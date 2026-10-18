"""Learn a wake sequence over a frozen, locally pretrained acoustic encoder.

The encoder's original zero classifier is only an initialization check. Its
ordered features retain consonant/vowel structure; no family audio is used here.
"""
import numpy as np
import tensorflow as tf


def attach(base,train_encoder=False):
    head=base.layers[-1]
    if not isinstance(head,tf.keras.layers.Dense) or head.units!=1 or any(np.any(w!=0) for w in head.get_weights()):
        raise ValueError('Acoustic sequence readout requires the explicit zero classifier from phonetic pretraining')
    pool=next(layer for layer in base.layers if isinstance(layer,tf.keras.layers.AveragePooling2D))
    features=pool.input
    if int(features.shape[1])<20 or int(features.shape[2])!=1:raise ValueError('Insufficient ordered acoustic context')
    # Explicit fine-tuning retains phonetic normalization statistics. The
    # integer identity anchor below must stay fixed in either experiment.
    for layer in base.layers:
        layer.trainable=bool(train_encoder) and not isinstance(layer,tf.keras.layers.BatchNormalization)
    x=tf.keras.layers.DepthwiseConv2D((1,1),use_bias=False,trainable=False,depthwise_initializer='ones',name='sequence_integer_anchor')(features)
    x=tf.keras.layers.DepthwiseConv2D((5,1),activation='relu',name='sequence_phone_pattern')(x)
    x=tf.keras.layers.Conv2D(16,(1,1),activation='relu',name='sequence_pattern_mix')(x)
    x=tf.keras.layers.AveragePooling2D((3,1),strides=(3,1))(x)
    x=tf.keras.layers.Flatten()(x);x=tf.keras.layers.Dense(32,activation='relu')(x);x=tf.keras.layers.Dropout(.1)(x)
    out=tf.keras.layers.Dense(1,activation='sigmoid',kernel_initializer='zeros',bias_initializer='zeros',name='sequence_wake_probability')(x)
    return tf.keras.Model(base.inputs[0],out)
