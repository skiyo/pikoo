"""Match the firmware's float32/half-away quantization and Micro reference kernels."""
import numpy as np
import tensorflow as tf


def interpreter(model):
    return tf.lite.Interpreter(model_path=str(model),num_threads=1,
        experimental_op_resolver_type=tf.lite.experimental.OpResolverType.BUILTIN_REF)


def quantize(features,scale,zero):
    # Firmware uses float32 followed by std::lround(value/scale) + zero_point.
    values=np.asarray(features,dtype=np.float32)/np.float32(scale)
    rounded=np.where(values>=0,np.floor(values+.5),np.ceil(values-.5))
    return np.clip(rounded+zero,-128,127).astype(np.int8)
