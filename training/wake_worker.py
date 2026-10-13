#!/usr/bin/env python3
"""Local microphone inference. PCM stdin; JSON events stdout. No recordings saved."""
import os
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','3')
import sys,json,time
from pathlib import Path
import numpy as np
import tensorflow as tf
from pymicro_features import MicroFrontend
model=Path(__file__).parent/'models/nihao_pikoo.tflite'
i=tf.lite.Interpreter(model_path=str(model),num_threads=1);i.allocate_tensors()
input_info=i.get_input_details()[0];output_info=i.get_output_details()[0]
f=MicroFrontend();frames=[];scores=[];last_detection=0
print(json.dumps({'type':'ready'}),flush=True)
while True:
    block=sys.stdin.buffer.read(320)  # 10ms PCM16 at 16kHz
    if len(block)!=320:break
    r=f.process_samples(block)
    if not r.features:continue
    frames.append(r.features)
    if len(frames)<3:continue
    scale,zero=input_info['quantization']
    x=np.clip(np.rint(np.asarray(frames)/scale+zero),-128,127).astype(np.int8)[None,...]
    frames=[];i.set_tensor(input_info['index'],x);i.invoke()
    scale,zero=output_info['quantization'];score=(int(i.get_tensor(output_info['index']).flat[0])-zero)*scale
    scores=(scores+[score])[-5:]
    if len(scores)==5 and sum(scores)/5>=.9 and time.monotonic()-last_detection>3:
        print(json.dumps({'type':'wake','score':sum(scores)/5}),flush=True)
        last_detection=time.monotonic()
