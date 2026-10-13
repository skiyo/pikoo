#!/usr/bin/env python3
"""Evaluate the exported streaming INT8 graph, not only its training model."""
import os
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','2')
import argparse,json,wave,hashlib
from pathlib import Path
import numpy as np
import tensorflow as tf
from pymicro_features import MicroFrontend

def predict(model,pcm):
    interpreter=tf.lite.Interpreter(model_path=str(model),num_threads=1)
    interpreter.allocate_tensors();inp=interpreter.get_input_details()[0];out=interpreter.get_output_details()[0]
    if inp['shape'].tolist()!=[1,3,40]:raise ValueError(f"Unexpected input shape {inp['shape']}")
    frontend=MicroFrontend();pending=[];prob=[]
    for i in range(0,len(pcm)-159,160):
        r=frontend.process_samples(pcm[i:i+160].astype('<i2').tobytes())
        if not r.features:continue
        pending.append(r.features)
        if len(pending)<3:continue
        scale,zero=inp['quantization'];x=np.clip(np.rint(np.array(pending)/scale+zero),-128,127).astype(np.int8)[None,...]
        pending=[];interpreter.set_tensor(inp['index'],x);interpreter.invoke()
        oscale,ozero=out['quantization'];prob.append((int(interpreter.get_tensor(out['index']).flat[0])-ozero)*oscale)
    rolling=np.convolve(prob,np.ones(5)/5,'valid') if len(prob)>=5 else np.array([0.])
    return float(max(rolling))

def main():
    p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--threshold',type=float,default=.9);a=p.parse_args()
    rows=json.loads(a.manifest.read_text());report={'status':'offline-evaluation-not-hardware-validated','threshold':a.threshold,'model_sha256':hashlib.sha256(a.model.read_bytes()).hexdigest(),'splits':{}}
    for split in ['validation','test']:
        result=[]
        for row in rows:
            if row['split']!=split:continue
            with wave.open(str(a.manifest.parent/row['path'])) as w:
                if (w.getnchannels(),w.getsampwidth(),w.getframerate())!=(1,2,16000):raise ValueError('Expected mono PCM16/16kHz')
                pcm=np.frombuffer(w.readframes(w.getnframes()),'<i2')
            score=predict(a.model,np.pad(pcm,(16000,16000)))
            result.append({'label':row['label'],'source':row.get('source','unknown'),'speaker':row.get('speaker',row.get('voice','unknown')),'age':row.get('age'),'real_child':row.get('real_child',False),'duration':len(pcm)/16000,'score':score,'detected':score>=a.threshold})
        pos=[r for r in result if r['label']];neg=[r for r in result if not r['label']]
        report['splits'][split]={'positive_clips':len(pos),'negative_clips':len(neg),'recall':sum(r['detected'] for r in pos)/len(pos) if pos else None,'false_positive_clips':sum(r['detected'] for r in neg),'details':result,'groups':{}}
        for key in ['source','speaker','age']:
            for value in {str(r[key]) for r in result}:
                group=[r for r in result if str(r[key])==value];p=[r for r in group if r['label']];n=[r for r in group if not r['label']]
                report['splits'][split]['groups'][key+':'+value]={'positive_clips':len(p),'detected_positive':sum(r['detected'] for r in p),'negative_clips':len(n),'false_positive_clips':sum(r['detected'] for r in n),'negative_audio_seconds':sum(r['duration'] for r in n),'real_child_clips':sum(r['real_child'] for r in group)}
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='splits'},ensure_ascii=False));print({s:{k:v for k,v in r.items() if k!='details'} for s,r in report['splits'].items()})
if __name__=='__main__':main()
