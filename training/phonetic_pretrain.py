#!/usr/bin/env python3
"""Research-only child/adult phonetic supervision for the causal wake encoder.

Only original TRAIN recordings with transcripts are eligible. Household, frozen
and evaluation audio are rejected by content. No voice cloning, concatenation,
network requests or raw transcript logging. Restricted derivatives stay private.
"""
import os
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','3')
import argparse,hashlib,json,re,sys,wave
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
import numpy as np


def phones(text):
    from pypinyin import pinyin,Style
    text=re.sub(r'pikoo|piku|pee[- ](?:koo|coo)','批枯',text,flags=re.I)
    if re.search('[A-Za-z0-9]',text):raise ValueError('Unnormalized transcript')
    text=''.join(re.findall('[\u4e00-\u9fff]',text))
    if not text:raise ValueError('Empty transcript')
    initial=pinyin(text,style=Style.INITIALS,strict=False,errors='ignore')
    final=pinyin(text,style=Style.FINALS,strict=False,errors='ignore')
    if len(initial)!=len(final):raise ValueError('Unaligned transcript')
    result=[]
    for i,f in zip(initial,final):
        if i[0]:result.append('i:'+i[0])
        if f[0]:result.append('f:'+f[0])
    return result


def eligible(row,protected):
    if row.get('evaluation_only') or row.get('frozen_holdout') or str(row.get('source','')).startswith('private-') or row.get('sha256') in protected:
        raise ValueError('Protected audio cannot enter acoustic pretraining')
    return row['split']=='train' and row['source'] in {'ChildMandarin','Qwen3-TTS-synthetic-local','Google-Gemini-TTS-synthetic'}


def flags(kernels=(5,9,13,21,31,43)):
    return SimpleNamespace(pointwise_filters=','.join(['128']*len(kernels)),repeat_in_block=','.join(['1']*len(kernels)),mixconv_kernel_sizes=','.join('['+str(k)+']' for k in kernels),residual_connection=','.join(['0']*len(kernels)),first_conv_filters=64,first_conv_kernel_size=3,stride=3,spatial_attention=0,pooled=1,max_pool=0)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['manifest','protected-hashes','permission-record','upstream','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--backbone-weights',type=Path)
    p.add_argument('--fresh',action='store_true',help='Fresh phonetic encoder, with trainable normalization; no inherited KWS weights')
    p.add_argument('--kernels',default='5,9,13,21,31,43',help='Causal acoustic kernels; short contexts are a separate phone-recognition experiment')
    p.add_argument('--epochs',type=int,default=24);p.add_argument('--limit',type=int,default=0);p.add_argument('--batch-size',type=int,default=16)
    a=p.parse_args();os.umask(0o077)
    kernels=[int(k) for k in a.kernels.split(',')]
    if not kernels or any(k<3 or k%2==0 for k in kernels):raise ValueError('Expected odd acoustic kernels >=3')
    left_context=3*sum(k-1 for k in kernels)
    if left_context>600 or (a.fresh==bool(a.backbone_weights)):raise ValueError('Choose fresh training or one explicit pretrained encoder')
    if not a.permission_record.is_file():raise ValueError('Existing authorized corpus permission record required')
    if not 1<=a.epochs<=60 or not 0<=a.limit<=10000:raise ValueError('Invalid bounded experiment')
    a.output.mkdir(parents=True,exist_ok=True)
    protected=set(json.loads(a.protected_hashes.read_text())['audio_sha256'].values());manifest=json.loads(a.manifest.read_text());rows=[];excluded=Counter()
    for row in manifest:
        # Official validation/test remain outside this task, never phonetic
        # supervision. Eligible() still rejects protected/renamed content.
        if not eligible(row,protected):continue
        path=a.manifest.parent/row['path'];digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=row['sha256'] or digest in protected:raise ValueError('Audio provenance mismatch')
        with wave.open(str(path)) as w:
            if (w.getnchannels(),w.getsampwidth(),w.getframerate())!=(1,2,16000):raise ValueError('Unexpected PCM format')
            duration=w.getnframes()/16000
        if not .3<=duration<=3.8:excluded['duration']+=1;continue
        try:tokens=phones(row['text'])
        except ValueError:excluded['transcript']+=1;continue
        if not 1<=len(tokens)<=72:excluded['label_length']+=1;continue
        speaker=row.get('speaker',row.get('voice',row['group']))
        fold='validation' if int(hashlib.sha256(('ctc-v1:'+speaker).encode()).hexdigest()[:8],16)%10==0 else 'train'
        rows.append({'row':row,'path':path,'tokens':tokens,'fold':fold})
    rows.sort(key=lambda x:x['row']['sha256'])
    if a.limit:rows=rows[:a.limit]
    vocabulary=sorted({t for x in rows if x['fold']=='train' for t in x['tokens']});ids={t:i+1 for i,t in enumerate(vocabulary)}
    rows=[x for x in rows if all(t in ids for t in x['tokens'])]
    if min(sum(x['fold']==s for x in rows) for s in ['train','validation'])<2:raise ValueError('No speaker-held-out acoustic validation')
    spec={'format':'phone-ctc-v1','frames':399,'left_context':left_context,'vocabulary':vocabulary,'rows':[{'sha256':x['row']['sha256'],'fold':x['fold'],'tokens':x['tokens']} for x in rows],'manifest_sha256':hashlib.sha256(a.manifest.read_bytes()).hexdigest(),'protected_sha256':hashlib.sha256(a.protected_hashes.read_bytes()).hexdigest()}
    fingerprint=hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest();cache=a.output/'features.npz';key=a.output/'features.sha256'
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(4);tf.config.threading.set_inter_op_parallelism_threads(2);tf.keras.utils.set_random_seed(2026101881)
    from train import load,features
    if cache.exists():
        if key.read_text().strip()!=fingerprint:raise ValueError('Acoustic feature cache provenance changed')
        arrays=np.load(cache);x,y,folds=arrays['x'],arrays['y'],arrays['folds']
    else:
        xs=[];ys=[];folds=[];retained=[]
        for index,item in enumerate(rows):
            pcm=load(item['path']);f=features(np.pad(pcm,(1600,1600)).astype('<i2'))
            n=min(399,len(f));length=(n+2)//3;tokens=[ids[t] for t in item['tokens']]
            if length<len(tokens)+sum(a==b for a,b in zip(tokens,tokens[1:])):excluded['ctc_alignment_length']+=1;continue
            x=np.zeros((399,40),np.float32);x[:n]=f[:n]
            y=np.zeros(74,np.int32);y[:2]=len(tokens),length;y[2:2+len(tokens)]=tokens
            xs.append(x);ys.append(y);folds.append(item['fold']=='validation');retained.append(item)
            if index%250==0:print(json.dumps({'acoustic_features':index+1,'total':len(rows)}),flush=True)
        rows=retained;x=np.asarray(xs);y=np.asarray(ys);folds=np.asarray(folds,bool)
        np.savez_compressed(cache,x=x,y=y,folds=folds);key.write_text(fingerprint+'\n')
    (a.output/'vocabulary.json').write_text(json.dumps({'blank':0,'tokens':ids},ensure_ascii=False,indent=2)+'\n')
    sys.path.insert(0,str(a.upstream));from microwakeword import mixednet
    from residual_readout import freeze_normalization
    backbone=mixednet.model(flags(kernels),(399+left_context,40),None)
    if a.backbone_weights:
        backbone.load_weights(a.backbone_weights);freeze_normalization(backbone)
    pool=next(l for l in backbone.layers if isinstance(l,tf.keras.layers.AveragePooling2D));stream=backbone.layers[backbone.layers.index(pool)-1]
    encoded=stream.input
    if tuple(encoded.shape[1:])!=(133,1,128):raise ValueError('Unexpected encoder causal alignment')
    encoder=tf.keras.Model(backbone.inputs,encoded,name='child_phonetic_encoder')
    inp=tf.keras.Input((399,40));z=tf.keras.layers.ZeroPadding1D((left_context,0))(inp);z=encoder(z)
    z=tf.keras.layers.Reshape((133,128))(z);logits=tf.keras.layers.Dense(len(vocabulary)+1,name='phone_logits')(z)
    model=tf.keras.Model(inp,logits)
    def loss(labels,logits):
        labels=tf.cast(labels,tf.int32)
        return tf.nn.ctc_loss(labels[:,2:],logits,labels[:,0],labels[:,1],logits_time_major=False,blank_index=0)
    model.compile(optimizer=tf.keras.optimizers.Adam(.0003,clipnorm=5),loss=loss)
    checkpoint=a.output/'phone-ctc.weights.h5'
    class Progress(tf.keras.callbacks.Callback):
        def on_epoch_end(self,epoch,logs=None):
            (a.output/'progress.json').write_text(json.dumps({'epoch':epoch+1,'logs':{k:float(v) for k,v in (logs or {}).items()},'household_used':False,'source':'authorized TRAIN public child plus modern fictional synthesis'},indent=2)+'\n')
    history=model.fit(x[~folds],y[~folds],validation_data=(x[folds],y[folds]),batch_size=a.batch_size,epochs=a.epochs,verbose=2,callbacks=[tf.keras.callbacks.ModelCheckpoint(str(checkpoint),save_best_only=True,save_weights_only=True),tf.keras.callbacks.EarlyStopping(patience=6,restore_best_weights=True),Progress()])
    model.load_weights(checkpoint)
    np.savez(a.output/'phone-head.npz',kernel=model.get_layer('phone_logits').get_weights()[0],bias=model.get_layer('phone_logits').get_weights()[1])
    # Readable phoneme error rate, without transcript/participant logging.
    errors=denominator=0
    for start in range(0,int(folds.sum()),16):
        labels=y[folds][start:start+16];logits=model(x[folds][start:start+16],training=False)
        decoded,_=tf.nn.ctc_greedy_decoder(tf.transpose(logits,[1,0,2]),labels[:,1],blank_index=0)
        truth=tf.sparse.from_dense(tf.cast(labels[:,2:],tf.int64))
        errors+=float(tf.reduce_sum(tf.edit_distance(decoded[0],truth,normalize=False)));denominator+=int(labels[:,0].sum())
    # A normal KWS checkpoint, with transferred acoustic layers and a fresh head.
    wake=mixednet.model(flags(kernels),(519,40),None);wake.set_weights(backbone.get_weights())
    head=wake.layers[-1];head.set_weights([np.zeros_like(v) for v in head.get_weights()]);wake.save_weights(a.output/'wake-encoder-init.weights.h5')
    sha=lambda file:hashlib.sha256(file.read_bytes()).hexdigest()
    (a.output/'phone-head.json').write_text(json.dumps({'encoder_init_sha256':sha(a.output/'wake-encoder-init.weights.h5'),'phone_head_sha256':sha(a.output/'phone-head.npz'),'ctc_weights_sha256':sha(checkpoint),'vocabulary_sha256':sha(a.output/'vocabulary.json'),'phoneme_classes':len(vocabulary)+1,'source_manifest_sha256':spec['manifest_sha256'],'household_used':False},indent=2)+'\n')
    report={'status':'completed-phonetic-pretraining-not-wake-acceptance','kernels':kernels,'left_context_frames':left_context,'fresh_encoder':a.fresh,'normalization_trainable':a.fresh,'train_clips':int((~folds).sum()),'speaker_heldout_validation_clips':int(folds.sum()),'phoneme_classes':len(vocabulary)+1,'phoneme_error_rate':errors/max(1,denominator),'epochs':len(history.history['loss']),'history':history.history,'permission_record_sha256':hashlib.sha256(a.permission_record.read_bytes()).hexdigest(),'manifest_sha256':spec['manifest_sha256'],'source_weights_sha256':hashlib.sha256(a.backbone_weights.read_bytes()).hexdigest() if a.backbone_weights else None,'household_used':False,'official_validation_or_test_used':False,'excluded':dict(excluded),'publication':'private restricted derivatives only','next':'Evaluate acoustic quality and initialize a separately validated wake model; no firmware promotion from CTC loss'}
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
