#!/usr/bin/env python3
"""Fail closed on model size, quantization and firmware operator compatibility.
This is static validation, not an ESP32 timing or peak-memory measurement.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '3')
from tensorflow.lite.python import schema_py_generated as schema

OP_METHODS = {
    'CALL_ONCE':'CallOnce', 'VAR_HANDLE':'VarHandle', 'READ_VARIABLE':'ReadVariable',
    'ASSIGN_VARIABLE':'AssignVariable', 'STRIDED_SLICE':'StridedSlice',
    'CONCATENATION':'Concatenation', 'CONV_2D':'Conv2D',
    'DEPTHWISE_CONV_2D':'DepthwiseConv2D', 'RESHAPE':'Reshape',
    'FULLY_CONNECTED':'FullyConnected', 'LOGISTIC':'Logistic',
    'AVERAGE_POOL_2D':'AveragePool2D', 'QUANTIZE':'Quantize',
    'DEQUANTIZE':'Dequantize', 'MUL':'Mul', 'ADD':'Add', 'MEAN':'Mean',
    'EXPAND_DIMS':'ExpandDims',
}


def check(path, firmware, max_bytes=65536):
    if not isinstance(max_bytes,int) or not 65536<=max_bytes<=524288:
        raise ValueError('Explicit model flash budget must be 64..512 KiB')
    binary = path.read_bytes()
    if len(binary) > max_bytes:
        raise ValueError(f'Model exceeds configured {max_bytes}-byte flash budget')
    model = schema.Model.GetRootAsModel(binary, 0)
    if model.Version() != 3:
        raise ValueError('Unsupported TFLite schema')
    names = {v:k for k,v in vars(schema.BuiltinOperator).items() if isinstance(v,int)}
    registered = set(re.findall(r'resolver\.Add(\w+)\(', firmware.read_text()))
    ops = []
    for i in range(model.OperatorCodesLength()):
        code = model.OperatorCodes(i); name = names.get(code.BuiltinCode(), 'UNKNOWN')
        if name not in OP_METHODS or OP_METHODS[name] not in registered:
            raise ValueError('Firmware has no registered operator: ' + name)
        ops.append(dict(name=name, version=code.Version()))
    graph=model.Subgraphs(0)
    if graph.InputsLength()!=1 or graph.OutputsLength()!=1:
        raise ValueError('Expected one streaming input and output')
    inp=graph.Tensors(graph.Inputs(0)); out=graph.Tensors(graph.Outputs(0))
    if inp.Type()!=schema.TensorType.INT8 or inp.ShapeAsNumpy().tolist()!=[1,3,40]:
        raise ValueError('Expected INT8 streaming input [1,3,40]')
    if out.Type() not in (schema.TensorType.UINT8, schema.TensorType.INT8) or int(out.ShapeAsNumpy().prod())!=1:
        raise ValueError('Expected one quantized probability')
    allowed={schema.TensorType.INT8,schema.TensorType.UINT8,schema.TensorType.INT32,
             schema.TensorType.INT64,schema.TensorType.RESOURCE,schema.TensorType.BOOL}
    for g in range(model.SubgraphsLength()):
        sub=model.Subgraphs(g)
        for t in range(sub.TensorsLength()):
            if sub.Tensors(t).Type() not in allowed:
                raise ValueError('Floating point or unsupported tensor in quantized model')
    return dict(status='static-check-passed', bytes=len(binary), flash_budget_bytes=max_bytes,
        sha256=hashlib.sha256(binary).hexdigest(), input_shape=[1,3,40], input_type='int8',
        feature_step_ms=10, inference_interval_ms=30, operators=ops,
        configured_tensor_arena_bytes=262144,
        hardware_status='Pending ESP32-S3 allocation, timing and concurrent audio/display tests')


def main():
    p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True)
    p.add_argument('--firmware',type=Path,default=Path(__file__).parents[1]/'firmware/main/wake_model.cpp')
    p.add_argument('--max-model-bytes',type=int,default=65536,help='Explicit experimental flash budget, 65536..524288; arena/timing still require measurement')
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=check(a.model,a.firmware,a.max_model_bytes);a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
