"""Preserve a trained wake encoder while learning ordered final time weights.

Average pooling discards the order of the encoder's last outputs. Initialize a
flattened temporal head to the exact same average, then train that head alone.
"""
import numpy as np
import tensorflow as tf


def attach(base):
    head=base.layers[-1]
    pools=[layer for layer in base.layers if isinstance(layer,tf.keras.layers.AveragePooling2D)]
    if not pools or not isinstance(head,tf.keras.layers.Dense) or head.units!=1:
        raise ValueError('Expected an average-pooled one-output wake encoder')
    pool=pools[-1];features=pool.input;steps=int(features.shape[1]);channels=int(features.shape[-1])
    if steps<2 or int(features.shape[2])!=1 or head.get_config()['activation']!='sigmoid':
        raise ValueError('Expected multiple ordered temporal outputs')
    kernel,bias=head.get_weights()
    if kernel.shape!=(channels,1):raise ValueError('Classifier does not match temporal channels')
    for layer in base.layers:layer.trainable=False
    # Keep the shared recurrent state quantizable even without average pooling.
    features=tf.keras.layers.DepthwiseConv2D((1,1),use_bias=False,trainable=False,
        depthwise_initializer='ones',name='temporal_integer_anchor')(features)
    features=tf.keras.layers.Flatten(name='temporal_ordered_features')(features)
    classifier=tf.keras.layers.Dense(1,activation='sigmoid',name='temporal_classifier')
    output=classifier(features)
    classifier.set_weights([np.tile(kernel,(steps,1))/steps,bias])
    return tf.keras.Model(base.inputs[0],output)
