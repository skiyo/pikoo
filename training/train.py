#!/usr/bin/env python3
"""Experimental microWakeWord training with speaker-disjoint data and INT8 export.
Requires the pinned upstream checkout via --upstream. Never fetches family audio.
"""
import os
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','2')
import argparse, json, hashlib, sys, wave
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from pymicro_features import MicroFrontend
import tensorflow as tf

def features(pcm):
    f=MicroFrontend();out=[]
    for i in range(0,len(pcm)-159,160):
        result=f.process_samples(pcm[i:i+160].astype('<i2').tobytes())
        if result.features:out.append(result.features)
    return np.asarray(out,np.float32)

def load(path):
    with wave.open(str(path)) as w:
        if w.getnchannels()!=1 or w.getframerate()!=16000 or w.getsampwidth()!=2:raise ValueError(f'expected mono PCM16/16kHz: {path.name}')
        return np.frombuffer(w.readframes(w.getnframes()),'<i2').astype(np.float32)

def dataset(manifest,root,seed=42):
    rng=np.random.default_rng(seed);sets={k:([],[]) for k in ['train','validation','test']}
    groups={};clips={}
    for row in manifest:
        group=row.get('speaker',row.get('voice',row['group']))
        if group in groups and groups[group]!=row['split']:raise ValueError('speaker/group leaks between splits')
        groups[group]=row['split'];digest=hashlib.sha256((root/row['path']).read_bytes()).hexdigest()
        if digest in clips and clips[digest]!=row['split']:raise ValueError('same recording appears across splits')
        clips[digest]=row['split']
        pcm=load(root/row['path'])
        # Each source is partitioned BEFORE augmentation.
        repeats=(32 if row['label'] else (1 if row.get('real_child') else 5)) if row['split']=='train' else 1
        for n in range(repeats):
            x=pcm.copy()
            if row['split']=='train':
                factor=rng.uniform(.88,1.12);x=np.interp(np.arange(0,len(x),factor),np.arange(len(x)),x)
                x*=rng.uniform(.35,1.2)
                if rng.random()<.5:
                    delay=int(rng.uniform(.03,.12)*16000);x[delay:]+=x[:-delay]*rng.uniform(.05,.25)
                x+=rng.normal(0,rng.uniform(0,150),len(x))
            # Sample ordinary speech throughout the clip, not only the last words.
            # Validation uses a fixed central window; streaming evaluation uses ALL audio.
            if not row['label'] and len(x)>32000:
                start=int(rng.integers(0,len(x)-32000+1)) if row['split']=='train' else (len(x)-32000)//2
                x=x[start:start+32000]
            # Wake phrase ends just before the prediction window ends.
            x=np.pad(x,(4800,int(rng.uniform(0,.12)*16000)))
            spec=features(np.clip(x,-32768,32767).astype(np.int16))
            if len(spec)<198:spec=np.pad(spec,((198-len(spec),0),(0,0)))
            spec=spec[-198:]
            sets[row['split']][0].append(spec);sets[row['split']][1].append(row['label'])
    # Negative silence and unstructured noise are needed, in addition to speech.
    for split in sets:
        for _ in range(100 if split=='train' else 20):
            pcm=rng.normal(0,rng.uniform(0,200),32000).astype(np.int16)
            sets[split][0].append(features(pcm)[-198:]);sets[split][1].append(0)
    return {k:(np.asarray(v[0],np.float32),np.asarray(v[1],np.float32)) for k,v in sets.items()}

def main():
    p=argparse.ArgumentParser();p.add_argument('--upstream',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--epochs',type=int,default=18);a=p.parse_args()
    sys.path.insert(0,str(a.upstream.resolve()))
    from microwakeword import mixednet,utils
    from microwakeword.layers import modes
    tf.keras.utils.set_random_seed(42);tf.config.threading.set_intra_op_parallelism_threads(4);tf.config.threading.set_inter_op_parallelism_threads(2)
    a.output.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(a.manifest.read_text());cache=a.output/'features.npz'
    fingerprint=hashlib.sha256(b'pikoo-features-v3-child-windows'+a.manifest.read_bytes())
    for row in manifest:fingerprint.update(hashlib.sha256((a.manifest.parent/row['path']).read_bytes()).digest())
    cache_key=fingerprint.hexdigest();keyfile=a.output/'features.sha256'
    if cache.exists() and keyfile.exists() and keyfile.read_text()==cache_key:
        data=np.load(cache);sets={s:(data[s+'_x'],data[s+'_y']) for s in ['train','validation','test']}
    else:
        sets=dataset(manifest,a.manifest.parent);np.savez_compressed(cache,**{s+'_'+k:v for s,pair in sets.items() for k,v in zip(['x','y'],pair)})
    keyfile.write_text(cache_key)
    print('sets', {s:len(v[1]) for s,v in sets.items()},flush=True)
    flags=SimpleNamespace(pointwise_filters='24,24,24,24',repeat_in_block='1,1,1,1',mixconv_kernel_sizes='[5],[9],[13],[21]',residual_connection='0,0,0,0',first_conv_filters=16,first_conv_kernel_size=3,stride=3,spatial_attention=0,pooled=1,max_pool=0)
    model=mixednet.model(flags,(198,40),None)
    model.compile(optimizer=tf.keras.optimizers.Adam(.001),loss='binary_crossentropy',metrics=['accuracy'])
    x,y=sets['train'];vx,vy=sets['validation'];tx,ty=sets['test']
    history=model.fit(x,y,batch_size=32,epochs=a.epochs,validation_data=(vx,vy),class_weight={0:1.,1:float((y==0).sum()/max(1,(y==1).sum()))},callbacks=[tf.keras.callbacks.EarlyStopping(monitor='val_loss',patience=5,restore_best_weights=True)],verbose=2)
    model.save_weights(a.output/'checkpoint.weights.h5')
    report={'status':'experimental','data_sources':{name:sum(r.get('source','unknown')==name for r in manifest) for name in set(r.get('source','unknown') for r in manifest)},'real_child_clips':sum(bool(r.get('real_child')) for r in manifest),'restricted_data':any(r.get('restricted',False) for r in manifest),'samples':{s:len(v[1]) for s,v in sets.items()},'epochs':len(history.history['loss']),'metrics':{}}
    for split,xx,yy in [('validation',vx,vy),('test',tx,ty)]:
        pred=model.predict(xx,verbose=0).reshape(-1);report['metrics'][split]={'positive_count':int(sum(yy==1)),'negative_count':int(sum(yy==0)),'window_recall_at_0.9':float(np.mean(pred[yy==1]>=.9)),'window_false_positive_rate_at_0.9':float(np.mean(pred[yy==0]>=.9))}
    config={'stride':3,'spectrogram_length':198}
    streaming=utils.to_streaming_inference(model,config,modes.Modes.STREAM_INTERNAL_STATE_INFERENCE)
    archive=tf.keras.export.ExportArchive();archive.track(streaming);archive.add_endpoint(name='serve',fn=streaming.call,input_signature=[tf.TensorSpec(streaming.input.shape,tf.float32)])
    archive.write_out(str(a.output/'saved'),verbose=False)
    # Calibrate across the training pool, including newly imported child speech,
    # rather than the first manifest entries (which can all be synthetic).
    calibration_rng=np.random.default_rng(43);calibration_indices=[]
    for label in (0,1):
        pool=np.flatnonzero(y==label)
        calibration_indices.extend(calibration_rng.choice(pool,min(50,len(pool)),replace=False).tolist())
    calibration_rng.shuffle(calibration_indices)
    def representative():
        for sample in x[calibration_indices]:
            for i in range(0,198,3):yield [sample[None,i:i+3,:].astype(np.float32)]
    converter=tf.lite.TFLiteConverter.from_saved_model(str(a.output/'saved'))
    converter.optimizations=[tf.lite.Optimize.DEFAULT];converter._experimental_variable_quantization=True
    converter.target_spec.supported_ops=[tf.lite.OpsSet.TFLITE_BUILTINS_INT8];converter.inference_input_type=tf.int8;converter.inference_output_type=tf.uint8;converter.representative_dataset=representative
    binary=converter.convert();(a.output/'nihao_pikoo.tflite').write_bytes(binary)
    from check_esp32_model import check
    compatibility=check(a.output/'nihao_pikoo.tflite',Path(__file__).parents[1]/'firmware/main/wake_model.cpp')
    (a.output/'esp32-static-check.json').write_text(json.dumps(compatibility,indent=2)+'\n')
    model_json={'type':'micro','wake_word':'你好皮酷','author':'Pikoo contributors','model':'nihao_pikoo.tflite','trained_languages':['zh'],'version':2,'micro':{'probability_cutoff':.90,'sliding_window_size':5,'feature_step_size':10,'tensor_arena_size':262144,'minimum_esphome_version':'2024.7'},'status':'experimental-not-hardware-validated'}
    (a.output/'nihao_pikoo.json').write_text(json.dumps(model_json,ensure_ascii=False,indent=2)+'\n')
    report.update(bytes=len(binary),sha256=hashlib.sha256(binary).hexdigest())
    (a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
