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
    if any(row.get('evaluation_only') or row.get('frozen_holdout') or str(row.get('source','')).startswith('private-') for row in manifest):
        raise ValueError('evaluation_only recordings require a separate evaluation manifest')

def dataset(manifest,root,seed=42,window_frames=198,positive_repeats=32,negative_repeats=5,hard_negative_repeats=5,min_snr=10,negative_prefixes=False,pcm_context=False,acoustic_augmentation=False,acoustic_probability=1.,negative_tail_seconds=.12,positive_tail_seconds=.12):
    validate_training_manifest(manifest)
    if not .12<=negative_tail_seconds<=1.5:raise ValueError('Negative tail must be between 0.12 and 1.5 seconds')
    if not .12<=positive_tail_seconds<=.6:raise ValueError('Positive tail must be between 0.12 and 0.6 seconds')
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
            # Non-targets must stay negative AFTER speech stops too. A short
            # end-aligned window misses delayed streaming false activations.
            # Keep positive alignment and validation/test construction intact.
            maximum_tail=negative_tail_seconds if row['split']=='train' and not row['label'] else .12
            if row['split']=='train' and row['label'] and positive_tail_seconds>.12:
                # Leave the complete target in the causal window, even after
                # speed augmentation. Never turn a cropped prefix positive.
                available=(window_samples-len(x)-4800)/16000
                if available<0:raise ValueError('Complete TRAIN target cannot fit; curate with --context-frames first')
                maximum_tail=min(positive_tail_seconds,available)
            tail=int(rng.uniform(0,maximum_tail)*16000)
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
    p.add_argument('--negative-tail-seconds',type=float,default=.12,help='TRAIN non-target tail range; 0.12..1.5 seconds; positive and evaluation alignment unchanged')
    p.add_argument('--positive-tail-seconds',type=float,default=.12,help='TRAIN complete-target tail range; 0.12..0.6 seconds, capped to preserve the entire phrase; evaluation unchanged')
    p.add_argument('--pcm-context',action='store_true',help='Use a complete noisy PCM context rather than zero feature padding')
    p.add_argument('--resume-weights',type=Path,help='Fine-tune a compatible local checkpoint; record its hash')
    p.add_argument('--negative-weight',type=float,default=1,help='Non-wake loss multiplier; calibrate on validation, not the test split')
    p.add_argument('--acoustic-augmentation',action='store_true',help='Synthetic band limits, early reflections, and -28 to +2dB gain; no household recordings')
    p.add_argument('--learning-rate',type=float,default=.001,help='Optimizer rate; use validation only to choose it')
    p.add_argument('--acoustic-probability',type=float,default=1.,help='Fraction of augmented training examples using acoustic simulation; others retain the baseline distribution')
    p.add_argument('--protected-hashes',type=Path,help='Reject household waveforms by content, including renamed files, before cache/quantization')
    p.add_argument('--widen-from',type=Path,help='Narrow checkpoint; preserve its function while adding independently initialized channels')
    p.add_argument('--source-filters',type=int,default=32)
    p.add_argument('--source-first-filters',type=int,default=24)
    p.add_argument('--max-model-bytes',type=int,default=65536,help='Explicit experimental flash budget, 65536..524288 bytes; does not change accuracy gates')
    p.add_argument('--save-epoch-checkpoints',action='store_true',help='Keep each private epoch for actual streaming development validation')
    p.add_argument('--export-only',action='store_true',help='Export a specified --resume-weights checkpoint without another training step; still checks provenance and quantization inputs')
    p.add_argument('--classifier-head-units',type=int,default=0,help='Optional 16..256-unit residual readout; freeze the original encoder and logit')
    p.add_argument('--head-backbone-weights',type=Path,help='Plain-model encoder initialization; resume is allowed only for export of a trained readout')
    p.add_argument('--freeze-batch-normalization',action='store_true',help='Fine-tune convolution weights while retaining pretrained normalization statistics')
    p.add_argument('--phonetic-readout',action='store_true',help='Experimental short-context causal correction branch; freezes the whole-phrase encoder')
    p.add_argument('--dropout',type=float,default=0.,help='Training-only dropout after encoder ReLUs; 0..0.4, plain model only')
    p.add_argument('--early-stop-patience',type=int,default=5,help='Window-validation patience; full streaming gate remains independent')
    p.add_argument('--phone-head',type=Path,help='Authorized CTC phone head with matching encoder metadata; freezes phonetic backbone')
    p.add_argument('--phone-logits',action='store_true',help='Use frozen phone logits instead of probabilities; separate quantization experiment')
    p.add_argument('--phone-logit-clip',type=float,default=0.,help='Optional 1..32 fixed logit bound for integer-friendly phone features')
    p.add_argument('--temporal-readout',action='store_true',help='Freeze the encoder and replace average pooling with an initially equivalent ordered head')
    p.add_argument('--sequence-readout',action='store_true',help='Train an ordered nonlinear wake head over an explicit zero-head phonetic encoder')
    p.add_argument('--train-sequence-encoder',action='store_true',help='Explicit joint acoustic-sequence experiment; retain pretrained normalization statistics')
    p.add_argument('--contrastive-classes',action='store_true',help='Separate complete near-phrase classes during sequence training; export scalar wake probability')
    p.add_argument('--relu6',action='store_true',help='Experimental bounded acoustic/sequence activations; requires explicit joint retraining and full revalidation')
    p.add_argument('--train-temporal-encoder',action='store_true',help='Train the ordered temporal head and its encoder jointly; separate fresh-training experiment')
    a=p.parse_args()
    os.umask(0o077)
    if not 65536<=a.max_model_bytes<=524288:raise ValueError('Model flash budget must be 64..512 KiB')
    if a.export_only and (not a.resume_weights or a.widen_from):raise ValueError('Export-only requires one explicit resume checkpoint')
    if a.classifier_head_units and not 16<=a.classifier_head_units<=256:raise ValueError('Classifier head must have 16..256 units')
    if a.head_backbone_weights and (not (a.classifier_head_units or a.phonetic_readout or a.temporal_readout or a.phone_head or a.sequence_readout) or (a.resume_weights and not a.export_only) or a.widen_from):raise ValueError('Head backbone requires a readout; resume is export-only and widening is separate')
    if a.sequence_readout and (not a.head_backbone_weights or a.classifier_head_units or a.phonetic_readout or a.temporal_readout or a.phone_head or a.dropout or a.widen_from):raise ValueError('Sequence readout requires only its explicit phonetic encoder initialization')
    if a.train_sequence_encoder and not a.sequence_readout:raise ValueError('Sequence encoder fine-tuning requires its explicit ordered head')
    if a.contrastive_classes and not a.sequence_readout:raise ValueError('Contrast supervision requires the explicit sequence readout')
    if a.phone_head and (not a.head_backbone_weights or a.temporal_readout or a.phonetic_readout or a.classifier_head_units or a.dropout or a.widen_from):raise ValueError('Phone bottleneck requires one explicit matching encoder initialization')
    if a.phone_logits and not a.phone_head:raise ValueError('Phone logits requires a matching phone head')
    if a.phone_logit_clip and (not a.phone_logits or not 1<=a.phone_logit_clip<=32):raise ValueError('Clip requires phone logits and a finite 1..32 bound')
    if a.temporal_readout and (a.classifier_head_units or a.phonetic_readout or a.widen_from or a.dropout):raise ValueError('Select one plain-encoder readout experiment')
    if a.train_temporal_encoder and not a.temporal_readout:raise ValueError('Joint temporal training requires the ordered head')
    if a.phonetic_readout and (a.classifier_head_units or a.widen_from):raise ValueError('Select one readout architecture')
    if a.freeze_batch_normalization and not (a.resume_weights or a.widen_from):raise ValueError('Frozen normalization requires explicit pretrained weights')
    if a.classifier_head_units and a.widen_from:raise ValueError('Widen the encoder and add a readout in separate experiments')
    if not 0<=a.dropout<=.4 or not 1<=a.early_stop_patience<=30:raise ValueError('Invalid regularization configuration')
    if a.dropout and (a.widen_from or a.classifier_head_units or a.phonetic_readout):raise ValueError('Dropout experiment requires a plain encoder')
    if not .12<=a.negative_tail_seconds<=1.5:raise ValueError('Negative tail must be between 0.12 and 1.5 seconds')
    if not .12<=a.positive_tail_seconds<=.6:raise ValueError('Positive tail must be between 0.12 and 0.6 seconds')
    if a.window_frames%3 or a.window_frames<150 or min(a.positive_repeats,a.negative_repeats,a.hard_negative_repeats,a.filters,a.first_filters)<1 or not 0<=a.min_snr<35 or not 0<a.negative_weight<=16 or not 0<a.learning_rate<=.01 or not 0<=a.acoustic_probability<=1:raise ValueError('Invalid training dimensions')
    kernels=[int(k) for k in a.kernels.split(',')]
    if a.relu6 and not (a.sequence_readout and a.train_sequence_encoder):raise ValueError('ReLU6 requires explicit joint sequence retraining')
    if not kernels or any(k<3 or k%2==0 for k in kernels) or a.window_frames//3<=sum(k-1 for k in kernels):raise ValueError('Receptive field exceeds training window')
    sys.path.insert(0,str(a.upstream.resolve()))
    from microwakeword import mixednet,utils
    from microwakeword.layers import modes
    tf.keras.utils.set_random_seed(42);tf.config.threading.set_intra_op_parallelism_threads(4);tf.config.threading.set_inter_op_parallelism_threads(2)
    a.output.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(a.manifest.read_text());cache=a.output/'features.npz'
    validate_training_manifest(manifest)
    protection=json.loads(a.protected_hashes.read_text()) if a.protected_hashes else {'audio_sha256':{}}
    protected=set(protection['audio_sha256'].values())
    household_count=protection.get('household_sha256_count',len(protected))
    if not isinstance(household_count,int) or not 0<=household_count<=len(protected):raise ValueError('Invalid protected household count')
    feature_config={'window_frames':a.window_frames,'positive_repeats':a.positive_repeats,'negative_repeats':a.negative_repeats,'hard_negative_repeats':a.hard_negative_repeats,'min_snr':a.min_snr,'negative_prefixes':a.negative_prefixes,'pcm_context':a.pcm_context,'acoustic_augmentation':a.acoustic_augmentation,'acoustic_probability':a.acoustic_probability,'negative_tail_seconds':a.negative_tail_seconds,'positive_tail_seconds':a.positive_tail_seconds}
    fingerprint=hashlib.sha256(b'pikoo-features-v5-mined-child-hard-negatives'+json.dumps(feature_config,sort_keys=True).encode()+a.manifest.read_bytes())
    for row in manifest:
        digest=hashlib.sha256((a.manifest.parent/row['path']).read_bytes()).digest()
        if digest.hex() in protected:raise ValueError('Protected household recording cannot enter training or quantization')
        fingerprint.update(digest)
    cache_key=fingerprint.hexdigest();keyfile=a.output/'features.sha256'
    if cache.exists() and keyfile.exists() and keyfile.read_text()==cache_key:
        data=np.load(cache);sets={s:(data[s+'_x'],data[s+'_y']) for s in ['train','validation','test']}
    else:
        sets=dataset(manifest,a.manifest.parent,**feature_config);np.savez_compressed(cache,**{s+'_'+k:v for s,pair in sets.items() for k,v in zip(['x','y'],pair)})
    keyfile.write_text(cache_key)
    print('sets', {s:len(v[1]) for s,v in sets.items()},flush=True)
    flags=SimpleNamespace(pointwise_filters=','.join([str(a.filters)]*len(kernels)),repeat_in_block=','.join(['1']*len(kernels)),mixconv_kernel_sizes=','.join('['+str(k)+']' for k in kernels),residual_connection=','.join(['0']*len(kernels)),first_conv_filters=a.first_filters,first_conv_kernel_size=3,stride=3,spatial_attention=0,pooled=1,max_pool=0)
    model=mixednet.model(flags,(a.window_frames,40),None)
    if a.dropout:
        from regularization import with_dropout
        model=with_dropout(model,a.dropout)
    widening=None
    if a.widen_from:
        if a.resume_weights:raise ValueError('Choose resume or widening, not both')
        source_flags=SimpleNamespace(**vars(flags));source_flags.pointwise_filters=','.join([str(a.source_filters)]*len(kernels));source_flags.first_conv_filters=a.source_first_filters
        source_model=mixednet.model(source_flags,(a.window_frames,40),None);source_model.load_weights(a.widen_from)
        from widen import warm_start_wider
        warm_start_wider(model,source_model)
        fixture=sets['train'][0][:8]
        difference=float(np.max(np.abs(model(fixture,training=False).numpy()-source_model(fixture,training=False).numpy())))
        if difference>1e-5:raise ValueError('Widening changed the original function')
        widening={'source_sha256':hashlib.sha256(a.widen_from.read_bytes()).hexdigest(),'initial_max_probability_difference':difference,'source_filters':a.source_filters,'source_first_filters':a.source_first_filters}
    readout=None
    if a.classifier_head_units or a.phonetic_readout or a.temporal_readout or a.phone_head or a.sequence_readout:
        if a.head_backbone_weights:model.load_weights(a.head_backbone_weights)
        if a.relu6:
            from regularization import with_relu6
            model=with_relu6(model)
        source_model=model
        if a.sequence_readout:
            from sequence_readout import attach
            model=attach(source_model,train_encoder=a.train_sequence_encoder,relu6=a.relu6)
        elif a.phone_head:
            from phonetic_bottleneck import attach
            model=attach(source_model,a.phone_head,a.head_backbone_weights,posterior=not a.phone_logits,logit_clip=a.phone_logit_clip)
        elif a.temporal_readout:
            from temporal_readout import attach
            model=attach(source_model)
        elif a.phonetic_readout:
            from phonetic_readout import attach
            model=attach(source_model)
        else:
            from residual_readout import attach
            model=attach(source_model,a.classifier_head_units)
        difference=float(np.max(np.abs(model(sets['train'][0][:8],training=False).numpy()-source_model(sets['train'][0][:8],training=False).numpy())))
        if difference>1e-5:raise ValueError('Residual initialization changed the original function')
        readout={'units':a.classifier_head_units,'backbone_frozen':True,'dropout':.1,'initial_max_probability_difference':difference}
        if a.phonetic_readout:readout.update(type='ordered-short-context-correction',channels=24,recent_frames=20,hidden_units=64)
        if a.phone_head:readout.update(type='frozen-phonetic-bottleneck',phone_input='logits' if a.phone_logits else 'probabilities',phone_logit_clip=a.phone_logit_clip,phone_head_sha256=hashlib.sha256(a.phone_head.read_bytes()).hexdigest())
        if a.temporal_readout:readout.update(type='ordered-final-temporal-head',hidden_units=0)
        if a.sequence_readout:readout.update(type='frozen-acoustic-sequence',hidden_units=32,channels=16)
        if a.train_sequence_encoder:readout.update(type='joint-acoustic-sequence',backbone_frozen=False,normalization_frozen=True)
        if a.relu6:readout.update(activation='relu6',changes_acoustic_function=True)
        if a.train_temporal_encoder:
            for layer in model.layers:
                if layer.name!='temporal_integer_anchor':layer.trainable=True
            readout.update(backbone_frozen=False,training='joint-encoder-and-ordered-head')
        if a.head_backbone_weights:readout['backbone_sha256']=hashlib.sha256(a.head_backbone_weights.read_bytes()).hexdigest()
    fit_model=model
    contrast_labels=None
    if a.contrastive_classes:
        from contrastive_readout import attach,expanded_labels,PHRASES
        fit_model,model=attach(model)
        contrast_labels=expanded_labels(manifest,a.positive_repeats,a.negative_repeats,a.hard_negative_repeats,a.negative_prefixes)
        for split,labels in contrast_labels.items():
            if len(labels)!=len(sets[split][1]) or not np.array_equal(labels==1,sets[split][1]==1):raise ValueError('Contrast labels do not match cached binary examples')
        readout.update(supervision='explicit-complete-near-phrase-classes',classes=PHRASES)
    if a.resume_weights:model.load_weights(a.resume_weights)
    if a.freeze_batch_normalization:
        from residual_readout import freeze_normalization
        freeze_normalization(model)
    fit_model.compile(optimizer=tf.keras.optimizers.Adam(a.learning_rate),loss='sparse_categorical_crossentropy' if a.contrastive_classes else 'binary_crossentropy',metrics=['accuracy'])
    x,y=sets['train'];vx,vy=sets['validation'];tx,ty=sets['test']
    weights={0:a.negative_weight,1:float((y==0).sum()/max(1,(y==1).sum()))}
    fit_y,fit_vy=y,vy
    if contrast_labels is not None:
        fit_y,fit_vy=contrast_labels['train'],contrast_labels['validation']
        counts={int(k):int((fit_y==k).sum()) for k in np.unique(fit_y)}
        weights={k:min(8.,max(1.,counts.get(0,1)/max(1,count)/max(1,len(counts)-2))) for k,count in counts.items()}
        weights[0]=a.negative_weight;weights[1]=float((y==0).sum()/max(1,(y==1).sum()))
    callbacks=[tf.keras.callbacks.EarlyStopping(monitor='val_loss',patience=a.early_stop_patience,restore_best_weights=True)]
    if a.save_epoch_checkpoints:
        (a.output/'epochs').mkdir(exist_ok=True)
        callbacks.append(tf.keras.callbacks.ModelCheckpoint(str(a.output/'epochs/epoch-{epoch:02d}.weights.h5'),save_weights_only=True))
    batch_rng=np.random.default_rng(42)
    def batches(values,labels,shuffle):
        def generate():
            order=np.arange(len(labels))
            if shuffle:batch_rng.shuffle(order)
            for start in range(0,len(order),32):
                selected=order[start:start+32];yield values[selected],labels[selected]
        data=tf.data.Dataset.from_generator(generate,output_signature=(tf.TensorSpec((None,a.window_frames,40),tf.float32),tf.TensorSpec((None,),tf.float32)))
        data=data.apply(tf.data.experimental.assert_cardinality((len(labels)+31)//32))
        options=tf.data.Options();options.threading.private_threadpool_size=2
        return data.with_options(options).prefetch(1)
    history=None if a.export_only else fit_model.fit(batches(x,fit_y,True),epochs=a.epochs,validation_data=batches(vx,fit_vy,False),class_weight=weights,callbacks=callbacks,shuffle=False,verbose=2)
    model.save_weights(a.output/'checkpoint.weights.h5')
    report={'status':'experimental','feature_config':feature_config,'filters':a.filters,'first_filters':a.first_filters,'kernels':kernels,'test_deferred':a.defer_test,'data_sources':{name:sum(r.get('source','unknown')==name for r in manifest) for name in set(r.get('source','unknown') for r in manifest)},'real_child_clips':sum(bool(r.get('real_child')) for r in manifest),'restricted_data':any(r.get('restricted',False) for r in manifest),'samples':{s:len(v[1]) for s,v in sets.items()},'epochs':len(history.history['loss']) if history else 0,'export_only':a.export_only,'metrics':{}}
    if history:(a.output/'training-history.json').write_text(json.dumps(history.history,indent=2)+'\n')
    if a.resume_weights:report['resume_weights_sha256']=hashlib.sha256(a.resume_weights.read_bytes()).hexdigest()
    report['class_weights']=weights
    report['learning_rate']=a.learning_rate
    report['training_manifest_sha256']=hashlib.sha256(a.manifest.read_bytes()).hexdigest()
    report['protected_household_hashes_checked']=household_count
    report['protected_audio_hashes_checked']=len(protected)
    if widening:report['widening']=widening
    if readout:report['classifier_readout']=readout
    report['batch_normalization_frozen']=a.freeze_batch_normalization
    report['training_regularization']={'dropout':a.dropout,'early_stop_patience':a.early_stop_patience}
    for split,xx,yy in [('validation',vx,vy),('test',tx,ty)]:
        if split=='test' and a.defer_test:continue
        pred=model.predict(xx,verbose=0).reshape(-1);report['metrics'][split]={'positive_count':int(sum(yy==1)),'negative_count':int(sum(yy==0)),'window_recall_at_0.9':float(np.mean(pred[yy==1]>=.9)),'window_false_positive_rate_at_0.9':float(np.mean(pred[yy==0]>=.9))}
    config={'stride':3,'spectrogram_length':a.window_frames}
    if a.phonetic_readout or a.phone_head:
        if a.phone_head:
            from phonetic_bottleneck import anchor_for_quantization
        else:
            from phonetic_readout import anchor_for_quantization
        before=model(x[:8],training=False).numpy()
        model=anchor_for_quantization(model)
        difference=float(np.max(np.abs(model(x[:8],training=False).numpy()-before)))
        if difference>1e-5:raise ValueError('Integer-state anchor changed the trained function')
        report['integer_state_anchor_max_difference']=difference
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
    # The pinned TF 2.18 reference FC kernel disagrees with optimized kernels
    # on multi-channel Dense quantization. Keep FC weights per-tensor so the
    # validation backend and Micro deployment use the same portable graph.
    converter._experimental_disable_per_channel_quantization_for_dense_layers=True
    converter.target_spec.supported_ops=[tf.lite.OpsSet.TFLITE_BUILTINS_INT8];converter.inference_input_type=tf.int8;converter.inference_output_type=tf.uint8;converter.representative_dataset=representative
    binary=converter.convert();(a.output/'nihao_pikoo.tflite').write_bytes(binary)
    report['dense_weight_quantization']='per-tensor; pinned reference-kernel portability'
    from check_esp32_model import check
    compatibility=check(a.output/'nihao_pikoo.tflite',Path(__file__).parents[1]/'firmware/main/wake_model.cpp',a.max_model_bytes)
    (a.output/'esp32-static-check.json').write_text(json.dumps(compatibility,indent=2)+'\n')
    model_json={'type':'micro','wake_word':'你好皮酷','author':'Pikoo contributors','model':'nihao_pikoo.tflite','trained_languages':['zh'],'version':2,'micro':{'probability_cutoff':.90,'sliding_window_size':5,'feature_step_size':10,'tensor_arena_size':262144,'minimum_esphome_version':'2024.7'},'status':'experimental-not-hardware-validated'}
    if any(r.get('pronunciation')=='mixed-pi1-ku1' and r['label'] and r['split']=='train' for r in manifest):
        model_json['trained_languages']=['zh','en']
        model_json['accepted_pronunciations']=['你好皮酷 / pi2-ku4','你好 Pikoo / pi1-ku1']
        model_json['language_scope']='Mandarin greeting with a mixed English pet name; not general English wake support'
        positives=[r for r in manifest if r['label'] and r['split']=='train']
        if all(r.get('pronunciation')=='mixed-pi1-ku1' for r in positives):
            model_json['wake_word']='你好 Pikoo'
            model_json['accepted_pronunciations']=['你好 Pikoo / pi1-ku1']
            model_json['pronunciation_scope']='Only level-tone pī kū is required; other tone variants are unspecified, not rejection targets'
    (a.output/'nihao_pikoo.json').write_text(json.dumps(model_json,ensure_ascii=False,indent=2)+'\n')
    report.update(bytes=len(binary),sha256=hashlib.sha256(binary).hexdigest(),max_model_bytes=a.max_model_bytes,parameters=model.count_params(),trainable_parameters=sum(int(np.prod(w.shape)) for w in model.trainable_weights))
    (a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
