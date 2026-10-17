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

def validate_training_manifest(manifest):
    # External acceptance recordings must never enter training, validation,
    # feature caches, or representative data for quantization.
    if any(row.get('evaluation_only') for row in manifest):
        raise ValueError('evaluation_only recordings require a separate evaluation manifest')

def dataset(manifest,root,seed=42,window_frames=198,positive_repeats=32,negative_repeats=5,hard_negative_repeats=5,min_snr=10,negative_prefixes=False,pcm_context=False,acoustic_augmentation=False,acoustic_probability=1.):
    validate_training_manifest(manifest)
    rng=np.random.default_rng(seed);sets={k:([],[]) for k in ['train','validation','test']}
    groups={};clips={}
    for row in manifest:
        group=row.get('speaker',row.get('voice',row['group']))
        if group in groups and groups[group]!=row['split']:raise ValueError('speaker/group leaks between splits')
        groups[group]=row['split'];digest=hashlib.sha256((root/row['path']).read_bytes()).hexdigest()
        if digest in clips and clips[digest]!=row['split']:raise ValueError('same recording appears across splits')
        clips[digest]=row['split']
        pcm=load(root/row['path'])
        if row['label'] and 'wake_end_sample' in row:
            end=int(row['wake_end_sample'])
            if not 0<end<=len(pcm):raise ValueError('Invalid labeled wake end')
            pcm=pcm[:end]  # The following sentence must not become a positive window.
        # Each source is partitioned BEFORE augmentation.
        repeats=(positive_repeats if row['label'] else (hard_negative_repeats if row.get('hard_negative') else 1 if row.get('real_child') else negative_repeats)) if row['split']=='train' else 1
        for n in range(repeats):
            x=pcm.copy()
            # Every causal prefix of a negative utterance is negative too. A
            # classifier trained only on sentence endings can fire mid-sentence.
            if negative_prefixes and not row['label'] and row['split']=='train' and n%2:
                x=x[:max(2880,int(len(x)*rng.uniform(.15,1.0)))]
            if row['split']=='train':
                factor=rng.uniform(.88,1.12);x=np.interp(np.arange(0,len(x),factor),np.arange(len(x)),x)
                use_acoustic=acoustic_augmentation and (acoustic_probability>=1 or rng.random()<acoustic_probability)
                if use_acoustic:
                    from acoustic_augment import augment
                    x=augment(x,rng)
                else:x*=rng.uniform(.35,1.2)
                if not use_acoustic and rng.random()<.5:
                    delay=int(rng.uniform(.03,.12)*16000);x[delay:]+=x[:-delay]*rng.uniform(.05,.25)
                if rng.random()<.7:
                    noise=np.sqrt(np.mean(x*x))/10**(rng.uniform(min_snr,35)/20)
                    x+=rng.normal(0,max(1,noise),len(x))
            # Sample ordinary speech throughout the clip, not only the last words.
            # Validation uses a fixed central window; streaming evaluation uses ALL audio.
            window_samples=(window_frames+2)*160
            if not row['label'] and len(x)>window_samples:
                start=int(rng.integers(0,len(x)-window_samples+1)) if row['split']=='train' else (len(x)-window_samples)//2
                x=x[start:start+window_samples]
            # Wake phrase ends just before the prediction window ends.
            tail=int(rng.uniform(0,.12)*16000)
            lead=max(4800,window_samples-len(x)-tail) if pcm_context else 4800
            x=np.pad(x,(lead,tail))
            if pcm_context:
                # A real idle microphone is not a zero-filled spectrogram.
                # Extract the entire causal window from quiet noisy PCM,
                # including the context before and after the wake phrase.
                x+=rng.normal(0,rng.uniform(2,80),len(x))
            spec=features(np.clip(x,-32768,32767).astype(np.int16))
            if len(spec)<window_frames:spec=np.pad(spec,((window_frames-len(spec),0),(0,0)))
            spec=spec[-window_frames:]
            sets[row['split']][0].append(spec);sets[row['split']][1].append(row['label'])
    # Negative silence and unstructured noise are needed, in addition to speech.
    for split in sets:
        for _ in range(100 if split=='train' else 20):
            pcm=rng.normal(0,rng.uniform(0,200),(window_frames+2)*160).astype(np.int16)
            sets[split][0].append(features(pcm)[-window_frames:]);sets[split][1].append(0)
    return {k:(np.asarray(v[0],np.float32),np.asarray(v[1],np.float32)) for k,v in sets.items()}

def main():
    p=argparse.ArgumentParser();p.add_argument('--upstream',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--epochs',type=int,default=18)
    p.add_argument('--window-frames',type=int,default=198);p.add_argument('--positive-repeats',type=int,default=32)
    p.add_argument('--negative-repeats',type=int,default=5);p.add_argument('--filters',type=int,default=24)
    p.add_argument('--first-filters',type=int,default=16);p.add_argument('--defer-test',action='store_true')
    p.add_argument('--kernels',default='5,9,13,21')
    p.add_argument('--hard-negative-repeats',type=int,default=5);p.add_argument('--min-snr',type=float,default=10)
    p.add_argument('--negative-prefixes',action='store_true')
    p.add_argument('--pcm-context',action='store_true',help='Use a complete noisy PCM context rather than zero feature padding')
    p.add_argument('--resume-weights',type=Path,help='Fine-tune a compatible local checkpoint; record its hash')
    p.add_argument('--negative-weight',type=float,default=1,help='Non-wake loss multiplier; calibrate on validation, not the test split')
    p.add_argument('--acoustic-augmentation',action='store_true',help='Synthetic band limits, early reflections, and -28 to +2dB gain; no household recordings')
    p.add_argument('--learning-rate',type=float,default=.001,help='Optimizer rate; use validation only to choose it')
    p.add_argument('--acoustic-probability',type=float,default=1.,help='Fraction of augmented training examples using acoustic simulation; others retain the baseline distribution')
    a=p.parse_args()
    os.umask(0o077)
    if a.window_frames%3 or a.window_frames<150 or min(a.positive_repeats,a.negative_repeats,a.hard_negative_repeats,a.filters,a.first_filters)<1 or not 0<=a.min_snr<35 or not 0<a.negative_weight<=16 or not 0<a.learning_rate<=.01 or not 0<=a.acoustic_probability<=1:raise ValueError('Invalid training dimensions')
    kernels=[int(k) for k in a.kernels.split(',')]
    if not kernels or any(k<3 or k%2==0 for k in kernels) or a.window_frames//3<=sum(k-1 for k in kernels):raise ValueError('Receptive field exceeds training window')
    sys.path.insert(0,str(a.upstream.resolve()))
    from microwakeword import mixednet,utils
    from microwakeword.layers import modes
    tf.keras.utils.set_random_seed(42);tf.config.threading.set_intra_op_parallelism_threads(4);tf.config.threading.set_inter_op_parallelism_threads(2)
    a.output.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(a.manifest.read_text());cache=a.output/'features.npz'
    validate_training_manifest(manifest)
    feature_config={'window_frames':a.window_frames,'positive_repeats':a.positive_repeats,'negative_repeats':a.negative_repeats,'hard_negative_repeats':a.hard_negative_repeats,'min_snr':a.min_snr,'negative_prefixes':a.negative_prefixes,'pcm_context':a.pcm_context,'acoustic_augmentation':a.acoustic_augmentation,'acoustic_probability':a.acoustic_probability}
    fingerprint=hashlib.sha256(b'pikoo-features-v5-mined-child-hard-negatives'+json.dumps(feature_config,sort_keys=True).encode()+a.manifest.read_bytes())
    for row in manifest:fingerprint.update(hashlib.sha256((a.manifest.parent/row['path']).read_bytes()).digest())
    cache_key=fingerprint.hexdigest();keyfile=a.output/'features.sha256'
    if cache.exists() and keyfile.exists() and keyfile.read_text()==cache_key:
        data=np.load(cache);sets={s:(data[s+'_x'],data[s+'_y']) for s in ['train','validation','test']}
    else:
        sets=dataset(manifest,a.manifest.parent,**feature_config);np.savez_compressed(cache,**{s+'_'+k:v for s,pair in sets.items() for k,v in zip(['x','y'],pair)})
    keyfile.write_text(cache_key)
    print('sets', {s:len(v[1]) for s,v in sets.items()},flush=True)
    flags=SimpleNamespace(pointwise_filters=','.join([str(a.filters)]*len(kernels)),repeat_in_block=','.join(['1']*len(kernels)),mixconv_kernel_sizes=','.join('['+str(k)+']' for k in kernels),residual_connection=','.join(['0']*len(kernels)),first_conv_filters=a.first_filters,first_conv_kernel_size=3,stride=3,spatial_attention=0,pooled=1,max_pool=0)
    model=mixednet.model(flags,(a.window_frames,40),None)
    if a.resume_weights:model.load_weights(a.resume_weights)
    model.compile(optimizer=tf.keras.optimizers.Adam(a.learning_rate),loss='binary_crossentropy',metrics=['accuracy'])
    x,y=sets['train'];vx,vy=sets['validation'];tx,ty=sets['test']
    weights={0:a.negative_weight,1:float((y==0).sum()/max(1,(y==1).sum()))}
    history=model.fit(x,y,batch_size=32,epochs=a.epochs,validation_data=(vx,vy),class_weight=weights,callbacks=[tf.keras.callbacks.EarlyStopping(monitor='val_loss',patience=5,restore_best_weights=True)],verbose=2)
    model.save_weights(a.output/'checkpoint.weights.h5')
    report={'status':'experimental','feature_config':feature_config,'filters':a.filters,'first_filters':a.first_filters,'kernels':kernels,'test_deferred':a.defer_test,'data_sources':{name:sum(r.get('source','unknown')==name for r in manifest) for name in set(r.get('source','unknown') for r in manifest)},'real_child_clips':sum(bool(r.get('real_child')) for r in manifest),'restricted_data':any(r.get('restricted',False) for r in manifest),'samples':{s:len(v[1]) for s,v in sets.items()},'epochs':len(history.history['loss']),'metrics':{}}
    if a.resume_weights:report['resume_weights_sha256']=hashlib.sha256(a.resume_weights.read_bytes()).hexdigest()
    report['class_weights']=weights
    report['learning_rate']=a.learning_rate
    for split,xx,yy in [('validation',vx,vy),('test',tx,ty)]:
        if split=='test' and a.defer_test:continue
        pred=model.predict(xx,verbose=0).reshape(-1);report['metrics'][split]={'positive_count':int(sum(yy==1)),'negative_count':int(sum(yy==0)),'window_recall_at_0.9':float(np.mean(pred[yy==1]>=.9)),'window_false_positive_rate_at_0.9':float(np.mean(pred[yy==0]>=.9))}
    config={'stride':3,'spectrogram_length':a.window_frames}
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
            for i in range(0,a.window_frames,3):yield [sample[None,i:i+3,:].astype(np.float32)]
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
