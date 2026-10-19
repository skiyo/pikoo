#!/usr/bin/env python3
"""Compare float and INT8 streaming probabilities on authorized TRAIN speech.

This catches export corruption before accuracy evaluation. It is not wake recall,
ESP32 timing, or household acceptance. No family or sealed test data is allowed.
"""
import argparse
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import numpy as np


def eligible(rows):
    if any(r.get('evaluation_only') or r.get('frozen_holdout') or str(r.get('source','')).startswith('private-') for r in rows):
        raise ValueError('Protected evaluation audio cannot debug quantization')
    groups={}
    for row in rows:
        if row['split']=='train':groups.setdefault((row['label'],row['source']),[]).append(row)
    queues={label:deque(key for key in groups if key[0]==label) for label in sorted({key[0] for key in groups})}
    chosen=[]
    while any(queues.values()):
        for queue in queues.values():
            if not queue:continue
            key=queue.popleft();chosen.append(groups[key].pop(0))
            if groups[key]:queue.append(key)
    return chosen


def errors(pairs):
    values=np.asarray(pairs,dtype=np.float64)
    if values.ndim!=2 or values.shape[1]!=2 or not len(values) or not np.isfinite(values).all() or values.min()<0 or values.max()>1:
        raise ValueError('Invalid streaming probability pairs')
    difference=np.abs(values[:,0]-values[:,1])
    worst=int(np.argmax(difference))
    return {'steps':len(values),'max_absolute_error':float(difference.max()),'mean_absolute_error':float(difference.mean()),
        'worst_step':worst,'float_at_worst':float(values[worst,0]),'int8_at_worst':float(values[worst,1])}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['model','saved','manifest','protected-hashes','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--limit',type=int,default=8)
    p.add_argument('--max-error',type=float,default=.15)
    p.add_argument('--mean-error',type=float,default=.03)
    a=p.parse_args();os.umask(0o077)
    if not 1<=a.limit<=32 or not 0<a.mean_error<=a.max_error<=1:raise ValueError('Invalid bounded parity check')
    rows=eligible(json.loads(a.manifest.read_text()))[:a.limit]
    if not rows:raise ValueError('No authorized TRAIN examples')
    protected=set(json.loads(a.protected_hashes.read_text())['audio_sha256'].values())
    os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','3')
    import tensorflow as tf
    from pymicro_features import MicroFrontend
    from streaming_runtime import interpreter,quantize
    from self_test import load
    results=[];model_sha=hashlib.sha256(a.model.read_bytes()).hexdigest()
    saved_hashes={str(f.relative_to(a.saved)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(a.saved.rglob('*')) if f.is_file()}
    for row in rows:
        path=a.manifest.parent/row['path'];digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in protected or digest!=row['sha256']:raise ValueError('Protected or changed TRAIN recording')
        floating=tf.saved_model.load(str(a.saved)).signatures['serve']
        runtime=interpreter(a.model);runtime.allocate_tensors();inp=runtime.get_input_details()[0];out=runtime.get_output_details()[0]
        if inp['shape'].tolist()!=[1,3,40]:raise ValueError('Expected the streaming microfrontend shape')
        pcm=np.pad(load(path),(16000,16000)).astype('<i2');frontend=MicroFrontend();pending=[];pairs=[]
        for offset in range(0,len(pcm)-159,160):
            features=frontend.process_samples(pcm[offset:offset+160].tobytes()).features
            if not features:continue
            pending.append(features)
            if len(pending)<3:continue
            answer=floating(tf.constant(np.asarray(pending,np.float32)[None]))
            if len(answer)!=1:raise ValueError('Expected one float probability output')
            probability=float(next(iter(answer.values())).numpy().flat[0])
            runtime.set_tensor(inp['index'],quantize(pending,*inp['quantization'])[None]);runtime.invoke()
            scale,zero=out['quantization'];integer=(int(runtime.get_tensor(out['index']).flat[0])-zero)*scale
            pairs.append((probability,integer));pending=[]
        metrics=errors(pairs);results.append({'sha256':digest,'source':row['source'],'label':row['label'],**metrics,
            'passed':metrics['max_absolute_error']<=a.max_error and metrics['mean_absolute_error']<=a.mean_error})
        print(json.dumps(results[-1]),flush=True)
    if hashlib.sha256(a.model.read_bytes()).hexdigest()!=model_sha:raise ValueError('Model changed during parity check')
    if saved_hashes!={str(f.relative_to(a.saved)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(a.saved.rglob('*')) if f.is_file()}:raise ValueError('Float model changed during parity check')
    report={'status':'passed-float-int8-diagnostic' if all(r['passed'] for r in results) else 'failed-float-int8-diagnostic',
        'model_sha256':model_sha,'saved_model_files_sha256':saved_hashes,
        'max_error_limit':a.max_error,'mean_error_limit':a.mean_error,'cases':results,'household_or_sealed_used':False,
        'scope':'small TRAIN-only engineering check, not accuracy or device acceptance'}
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    if any(not r['passed'] for r in results):raise SystemExit(2)


if __name__=='__main__':main()
