"""Training-only dropout; inference retains the original convolution topology."""
import math
import tensorflow as tf


def with_relu6(base):
    """Bound acoustic ReLUs before explicit retraining, preserving all weights.

    This changes the acoustic function and is not a transparent export fix.
    In particular, it must not promote an old checkpoint without revalidation.
    """
    def clone(layer):
        config=layer.get_config()
        if isinstance(layer,tf.keras.layers.Activation) and config['activation']=='relu':
            config['activation']='relu6'
        return layer.__class__.from_config(config)
    model=tf.keras.models.clone_model(base,clone_function=clone)
    model.set_weights(base.get_weights())
    return model


def with_dropout(base,rate):
    if not math.isfinite(rate) or not 0<rate<=.4:raise ValueError('Dropout must be in (0, 0.4]')
    def call(layer,*args,**kwargs):
        result=layer(*args,**kwargs)
        if isinstance(layer,tf.keras.layers.Activation) and layer.get_config()['activation']=='relu':
            result=tf.keras.layers.Dropout(rate,name=layer.name+'_training_dropout')(result)
        return result
    model=tf.keras.models.clone_model(base,call_function=call)
    model.set_weights(base.get_weights())
    return model
