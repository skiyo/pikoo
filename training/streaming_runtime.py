"""Match the firmware's float32/half-away quantization and Micro reference kernels."""
import numpy as np
import tensorflow as tf
from tensorflow.lite.python import schema_py_generated as schema
from pathlib import Path


def validate_reference_quantization(binary):
    model=schema.Model.GetRootAsModel(binary,0)
    for i in range(model.SubgraphsLength()):
        graph=model.Subgraphs(i)
        for j in range(graph.OperatorsLength()):
            op=graph.Operators(j)
            if model.OperatorCodes(op.OpcodeIndex()).BuiltinCode()!=schema.BuiltinOperator.FULLY_CONNECTED:continue
            weight=graph.Tensors(op.Inputs(1));quant=weight.Quantization()
            if quant and quant.ScaleLength()>1:
                raise ValueError('Per-channel FullyConnected is excluded by the pinned reference portability policy; re-export with per-tensor Dense weights before scoring')


def interpreter(model):
    validate_reference_quantization(Path(model).read_bytes())
    return tf.lite.Interpreter(model_path=str(model),num_threads=1,
        experimental_op_resolver_type=tf.lite.experimental.OpResolverType.BUILTIN_REF)


def quantize(features,scale,zero):
    # Firmware uses float32 followed by std::lround(value/scale) + zero_point.
    values=np.asarray(features,dtype=np.float32)/np.float32(scale)
    rounded=np.where(values>=0,np.floor(values+.5),np.ceil(values-.5))
    return np.clip(rounded+zero,-128,127).astype(np.int8)
