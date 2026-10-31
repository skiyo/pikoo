#!/usr/bin/env python3
"""Local microphone inference. PCM stdin; JSON events stdout. No recordings saved."""
import os
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','3')
import sys,json,time,hashlib
from pathlib import Path
import numpy as np
import tensorflow as tf
from pymicro_features import MicroFrontend
from streaming_runtime import interpreter as create_interpreter,quantize
from hi_pikoo_model import RollingDecision
if not os.environ.get('PIKOO_WAKE_MODEL'):
    raise SystemExit('Set PIKOO_WAKE_MODEL to an authorized local model. No model weights are distributed.')
model=Path(os.environ['PIKOO_WAKE_MODEL'])
policy_path=Path(os.environ.get('PIKOO_WAKE_POLICY',str(model.parent/'wake-policy.json')))
policy={'rolling':5,'threshold':.9,'target':'legacy-nihao-pikoo'}
if policy_path.exists():
    sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
    from check_wake_policy import validate
    policy=validate(model,json.loads(policy_path.read_text()),os.environ.get('PIKOO_ALLOW_TRIAL_WAKE')=='1')
elif os.environ.get('PIKOO_WAKE_POLICY') or model.name=='hi_pikoo.tflite':
    raise SystemExit('Hi Pikoo requires a matching frozen wake policy.')
i=create_interpreter(model);i.allocate_tensors()
input_info=i.get_input_details()[0];output_info=i.get_output_details()[0]
f=MicroFrontend();frames=[];decision=RollingDecision(policy['rolling']);last_detection=0;last_score_time=0;steps=0
print(json.dumps({'type':'ready','modelSha256':hashlib.sha256(model.read_bytes()).hexdigest(),'target':policy['target'],'acceptedNames':policy.get('accepted_names',['piku']),'threshold':policy['threshold'],'rolling':policy['rolling'],'trial':policy.get('trial_authorized',False)}),flush=True)
while True:
    block=sys.stdin.buffer.read(320)  # 10ms PCM16 at 16kHz
    if len(block)!=320:break
    r=f.process_samples(block)
    if not r.features:continue
    frames.append(r.features)
    if len(frames)<3:continue
    scale,zero=input_info['quantization']
    x=quantize(frames,scale,zero)[None,...]
    frames=[];i.set_tensor(input_info['index'],x);i.invoke()
    scale,zero=output_info['quantization'];score=(int(i.get_tensor(output_info['index']).flat[0])-zero)*scale
    average=float(decision.feed(score));steps+=1
    now=time.monotonic()
    if steps>=policy['rolling'] and now-last_score_time>=.1:
        print(json.dumps({'type':'score','score':average}),flush=True)
        last_score_time=now
    if steps>=policy['rolling'] and average>=policy['threshold'] and time.monotonic()-last_detection>3:
        print(json.dumps({'type':'wake','score':average}),flush=True)
        last_detection=time.monotonic()
