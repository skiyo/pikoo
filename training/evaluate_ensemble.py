#!/usr/bin/env python3
"""Full causal development evaluation, never household or sealed selection.

Two independent interpreters share only the exact causal microfrontend features.
Agreement uses five-step means and a ten-step past-only coincidence window.
"""
import argparse,hashlib,json,os
from pathlib import Path
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','3')
os.environ.setdefault('TF_NUM_INTRAOP_THREADS','1')
os.environ.setdefault('TF_NUM_INTEROP_THREADS','1')
import numpy as np
from pymicro_features import MicroFrontend
from streaming_runtime import interpreter,quantize
from self_test import load
from ensemble_runtime import Agreement
from streaming_gate import assess,legacy_targets


def predict(models,pcm,threshold_a=.8,threshold_b=.8):
    engines=[]
    for model in models:
        runtime=interpreter(model);runtime.allocate_tensors()
        engines.append((runtime,runtime.get_input_details()[0],runtime.get_output_details()[0]))
    frontend=MicroFrontend();pending=[];agreement=Agreement(threshold_a,secondary_threshold=threshold_b);peak=0;first=None;steps=0
    for offset in range(0,len(pcm)-159,160):
        features=frontend.process_samples(pcm[offset:offset+160].astype('<i2').tobytes()).features
        if not features:continue
        pending.append(features)
        if len(pending)<3:continue
        probabilities=[]
        for runtime,inp,out in engines:
            runtime.set_tensor(inp['index'],quantize(pending,*inp['quantization'])[None]);runtime.invoke()
            scale,zero=out['quantization'];probabilities.append((int(runtime.get_tensor(out['index']).flat[0])-zero)*scale)
        pending=[];steps+=1;score=agreement.step(*probabilities);peak=max(peak,score)
        if first is None and score>=agreement.threshold:first=offset+160
    return peak,first,steps


def main():
    p=argparse.ArgumentParser()
    for name in ['manifest','model-a','model-b','policy','legacy-manifest','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--threshold-a',type=float,default=.8)
    p.add_argument('--threshold-b',type=float,default=.8)
    a=p.parse_args();os.umask(0o077);rows=[x for x in json.loads(a.manifest.read_text()) if x['split']=='validation'];models=[a.model_a,a.model_b];hashes=[hashlib.sha256(x.read_bytes()).hexdigest() for x in models];details=[]
    for index,row in enumerate(rows):
        if row.get('evaluation_only') or row.get('frozen_holdout') or row['source'].startswith('private-'):raise ValueError('Protected audio is not eligible')
        source=a.manifest.parent/row['path'];assert hashlib.sha256(source.read_bytes()).hexdigest()==row['sha256']
        pcm=load(source).astype('<i2');score,first,steps=predict(models,np.pad(pcm,(16000,16000)),a.threshold_a,a.threshold_b)
        details.append({**{k:row.get(k) for k in ['label','source','sha256','speaker','real_child','pronunciation','synthetic_style','evaluation_only','frozen_holdout','context']},'condition':'clean','seconds':len(pcm)/16000,'scores':{'candidate':score},'detected':{'candidate':first is not None},'first_trigger_sample':first,'steps':steps})
        if index%50==0:print(json.dumps({'scored':index+1,'total':len(rows)}),flush=True)
    contract='causal-agreement-v1:'+':'.join(hashes)+':threshold.8:rolling5:past10' if a.threshold_a==a.threshold_b==.8 else 'causal-agreement-v2:'+':'.join(hashes)+f':cutoffs{a.threshold_a!r}/{a.threshold_b!r}:rolling5:past10'
    identity=hashlib.sha256(contract.encode()).hexdigest()
    evaluation={'status':'causal-ensemble-development-not-human-acceptance','threshold':a.threshold_a,'member_thresholds':[a.threshold_a,a.threshold_b],'models':{'candidate':identity},'member_models':hashes,'input_context':{'lead_seconds':1.,'background_rms':0.},'details':details,'household_used':False,'sealed_test_scored':False}
    assert hashes==[hashlib.sha256(x.read_bytes()).hexdigest() for x in models]
    policy=json.loads(a.policy.read_text());report=assess(evaluation,policy,legacy_targets(json.loads(a.legacy_manifest.read_text())),sum(x.stat().st_size for x in models));report.update(pipeline='two causal INT8 networks, each rolling5, past-only10-step agreement',member_models=hashes,policy=policy,hardware_status='pending dual-core timing, allocation and microphone tests',sealed_test_scored=False)
    a.output.write_text(json.dumps(evaluation,indent=2)+'\n');a.output.with_suffix('.gate.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
