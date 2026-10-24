"""Export-only Dense substitution for per-output-channel convolution weights.

The pinned FullyConnected reference path excludes per-channel weights. A 1x1
Conv2D applies the same affine function and has independently tested per-channel
kernels. This is not a change to training checkpoints or a quality-gate waiver.
"""
import tensorflow as tf


def replace_dense(model):
    original={layer.name:layer for layer in model.layers}
    created=set();replaced=[]
    def call(layer,*args,**kwargs):
        if not isinstance(layer,tf.keras.layers.Dense):return layer(*args,**kwargs)
        value=args[0]
        if len(value.shape) not in (2,4) or value.shape[-1] is None:
            raise ValueError('Dense convolution export requires known rank-two or rank-four features')
        names=[layer.name+suffix for suffix in ['_conv_input','_quant_conv','_conv_output']]
        if any(name in original for name in names):raise ValueError('Dense export name collision')
        created.update(names)
        conv=tf.keras.layers.Conv2D(layer.units,(1,1),activation=layer.activation,
            use_bias=layer.use_bias,trainable=layer.trainable,name=names[1])
        output=conv(tf.keras.layers.Reshape((1,1,int(value.shape[-1])),name=names[0])(value)) if len(value.shape)==2 else conv(value)
        weights=original[layer.name].get_weights()
        conv.set_weights([weights[0].reshape(1,1,*weights[0].shape),*weights[1:]])
        replaced.append(layer.name)
        return tf.keras.layers.Reshape((layer.units,),name=names[2])(output) if len(value.shape)==2 else output
    converted=tf.keras.models.clone_model(model,call_function=call)
    copied=set()
    for layer in converted.layers:
        if isinstance(layer,tf.keras.layers.InputLayer) or layer.name in created:continue
        if layer.name not in original:raise ValueError('Export added an unexplained layer')
        layer.set_weights(original[layer.name].get_weights());copied.add(layer.name)
    expected={name for name,layer in original.items() if not isinstance(layer,tf.keras.layers.InputLayer)}
    if copied|set(replaced)!=expected:raise ValueError('Export lost an original layer')
    if not replaced:raise ValueError('No Dense layer to replace')
    return converted,{'method':'Dense-as-1x1-Conv2D','layers':replaced,'training_checkpoint_changed':False}
