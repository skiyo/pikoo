#!/usr/bin/env python3
"""Compare TF Lite with the pinned Micro reference runtime on identical features.
This tests recurrent resets as well as actual scores; it is not ESP-NN timing.
"""
import argparse
import json
import hashlib
from pathlib import Path
import subprocess
import tempfile
import numpy as np
import tensorflow as tf
from train import features,load
from evaluate import predict
from streaming_runtime import interpreter as create_interpreter,quantize


def main():
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--model',type=Path,required=True);p.add_argument('--micro-check',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    rows=json.loads(a.manifest.read_text());cases=[]
    for label in [1,0]:
        cases.extend([r for r in rows if r['split']=='validation' and r['label']==label and not r.get('real_child')][:3])
    results=[]
    for row in cases:
        pcm=np.pad(load(a.manifest.parent/row['path']).astype(np.int16),(16000,16000))
        spec=features(pcm);spec=spec[:len(spec)//3*3]
        interpreter=create_interpreter(a.model);interpreter.allocate_tensors()
        inp=interpreter.get_input_details()[0];scale,zero=inp['quantization']
        quant=quantize(spec,scale,zero)
        with tempfile.TemporaryDirectory() as tmp:
            fixture=Path(tmp)/'features.bin';fixture.write_bytes(quant.tobytes())
            r=subprocess.run([str(a.micro_check.resolve()),str(a.model.resolve()),str(fixture)],capture_output=True,text=True,check=True)
            micro=json.loads(r.stdout)
        reference=predict(a.model,pcm)
        assert max(micro['peaks'])-min(micro['peaks'])<.00001,'State reset changes predictions'
        assert max(abs(v-reference) for v in micro['peaks'])<=.02,'Micro/reference predictions differ'
        results.append({'label':row['label'],'context':row.get('context'),'tf_reference_peak':reference,
                        'micro_peaks':micro['peaks'],'host_arena_used_bytes':micro['host_arena_used_bytes']})
    report={'status':'host-micro-parity-passed','model_sha256':hashlib.sha256(a.model.read_bytes()).hexdigest(),
            'runtime':'TFLite BUILTIN_REF; float32 half-away quantization matching firmware',
            'cases':len(cases),'resets_per_case':3,'score_tolerance':.02,
            'esp32_hardware_validated':False,'details':results}
    a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
