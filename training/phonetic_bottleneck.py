"""Freeze supervised phonetic features and learn a small ordered wake head.

The phone head and encoder must come from the same authorized local CTC run.
No recordings or pretrained weights are distributed with this module.
"""
import hashlib,json
from pathlib import Path
import numpy as np
import tensorflow as tf


def attach(base,phone_head,encoder_weights,posterior=True,logit_clip=0.):
    meta=json.loads(phone_head.with_suffix('.json').read_text())
    if hashlib.sha256(phone_head.read_bytes()).hexdigest()!=meta['phone_head_sha256']:
        raise ValueError('Phone head checksum mismatch')
    if hashlib.sha256(encoder_weights.read_bytes()).hexdigest()!=meta['encoder_init_sha256']:
        raise ValueError('Phone head does not match the frozen acoustic encoder')
    weights=np.load(phone_head);kernel,bias=weights['kernel'],weights['bias']
    pool=next(l for l in base.layers if isinstance(l,tf.keras.layers.AveragePooling2D))
    history=base.layers[base.layers.index(pool)-1];x=history.input
    steps,channels=int(x.shape[1]),int(x.shape[-1])
    if steps<20 or kernel.shape[0]!=channels or not 40<=kernel.shape[1]<=128 or bias.shape!=(kernel.shape[1],):
        raise ValueError('Unexpected phonetic bottleneck dimensions')
    for layer in base.layers:layer.trainable=False
    if logit_clip:
        if posterior or not np.isfinite(logit_clip) or not 1<=logit_clip<=32:raise ValueError('Bounded logits requires a finite 1..32 clip without Softmax')
        # Fixed affine transform maps [-clip,+clip] to the standard integer
        # ReLU6 range. This prevents rare CTC logit outliers dominating PTQ.
        kernel,bias=kernel*(3/logit_clip),bias*(3/logit_clip)+3
    phone=tf.keras.layers.Dense(len(bias),trainable=False,name='frozen_phone_logits');x=phone(x);phone.set_weights([kernel,bias])
    if posterior:x=tf.keras.layers.Softmax(axis=-1,name='frozen_phone_probabilities')(x)
    elif logit_clip:x=tf.keras.layers.ReLU(max_value=6.,name='bounded_phone_logits')(x)
    # A fresh Stream instance is necessary because the original history has the
    # encoder channel count, while this one stores quantized phone posteriors.
    x=history.__class__(cell=tf.keras.layers.Identity(),ring_buffer_size_in_time_dim=steps-1,use_one_step=False)(x)
    x=tf.keras.layers.DepthwiseConv2D((1,1),use_bias=False,trainable=False,depthwise_initializer='ones',name='phone_integer_anchor')(x)
    x=tf.keras.layers.DepthwiseConv2D((5,1),activation='relu',name='phone_temporal_pattern')(x)
    x=tf.keras.layers.Conv2D(16,(1,1),activation='relu',name='phone_pattern_mix')(x)
    x=tf.keras.layers.AveragePooling2D((3,1),strides=(3,1))(x)
    x=tf.keras.layers.Flatten()(x);x=tf.keras.layers.Dense(32,activation='relu')(x);x=tf.keras.layers.Dropout(.1)(x)
    output=tf.keras.layers.Dense(1,activation='sigmoid',kernel_initializer='zeros',bias_initializer='zeros',name='phone_wake_classifier')(x)
    return tf.keras.Model(base.inputs[0],output)


def anchor_for_quantization(base):
    """Isolate the fixed Softmax scale from the calibrated recurrent state.

    TF 2.18 otherwise assigns 1/256 to Softmax and 1/255 to its history,
    violating integer Concat's equal-scale requirement. The exact unit kernel
    permits an explicit integer rescale without changing the float function.
    Insert it only at export, preserving existing training checkpoints.
    """
    name='phone_export_scale_anchor'
    def call(layer,*args,**kwargs):
        result=layer(*args,**kwargs)
        if layer.name=='frozen_phone_probabilities':
            result=tf.keras.layers.DepthwiseConv2D((1,1),use_bias=False,trainable=False,
                depthwise_initializer='ones',name=name)(result)
        return result
    model=tf.keras.models.clone_model(base,call_function=call)
    original={layer.name:layer for layer in base.layers if not isinstance(layer,tf.keras.layers.InputLayer)}
    copied=set()
    for layer in model.layers:
        if layer.name==name or isinstance(layer,tf.keras.layers.InputLayer):continue
        if layer.name not in original:raise ValueError('Export changed a phonetic layer')
        layer.set_weights(original[layer.name].get_weights());copied.add(layer.name)
    if copied!=set(original):raise ValueError('Export lost a phonetic layer')
    return model
