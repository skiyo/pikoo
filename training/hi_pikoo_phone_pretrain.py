#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fresh small acoustic encoder from original authorized public TRAIN speech.

CTC is training-only. No historical wake classifier/household/official TEST,
no cropped utterance paired with a full transcript, no downloads/cloud calls.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import wave
import numpy as np
from phonetic_pretrain import phones, eligible
from hi_pikoo_train import read_audio, features_and_times


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ctc_loss(labels, output):
    import tensorflow as tf
    labels=tf.cast(labels,tf.int32)
    return tf.nn.ctc_loss(labels[:,2:2+tf.reduce_max(labels[:,0])],
        output[:,:tf.reduce_max(labels[:,1])],labels[:,0],labels[:,1],
        logits_time_major=False,blank_index=0)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ('manifest', 'protected-hashes', 'permission-record', 'upstream', 'output'):
        p.add_argument('--'+flag, type=Path, required=True)
    p.add_argument('--epochs', type=int, default=16)
    p.add_argument('--channels', type=int, choices=(48,96), default=48)
    p.add_argument('--feature-cache-source', type=Path)
    p.add_argument('--resume-ctc', type=Path)
    a = p.parse_args()
    if not 1 <= a.epochs <= 24 or not a.permission_record.is_file():
        raise ValueError('Bounded experiment and existing corpus permission required')
    if a.resume_ctc and not a.feature_cache_source:
        raise ValueError('Own checkpoint continuation requires its exact feature cache')
    os.umask(0o077)
    a.output.mkdir(parents=True, exist_ok=False)
    snapshot = a.output/'source-snapshot'
    snapshot.mkdir()
    for name in ('hi_pikoo_phone_pretrain.py', 'hi_pikoo_model.py', 'hi_pikoo_train.py',
                 'hi_pikoo_contrast.py', 'hi_pikoo_timing.py', 'phonetic_pretrain.py'):
        shutil.copyfile(Path(__file__).with_name(name), snapshot/name)
    protected = set(json.loads(a.protected_hashes.read_text())['audio_sha256'].values())
    manifest = json.loads(a.manifest.read_text())
    rows, excluded = [], Counter()
    for row in manifest:
        if row.get('source') not in {'ChildMandarin', 'PolyAI-MInDS14-zh-CN'}:
            excluded['not-original-public-speech'] += 1
            continue
        if not eligible(row, protected) or row.get('split') != 'train':
            raise ValueError('Only unprotected official TRAIN originals are allowed')
        if row['source'] == 'ChildMandarin' and not row.get('original_full_utterance'):
            raise ValueError('Original full child utterance required')
        path = (a.manifest.parent/row['path']).resolve()
        if sha(path) != row['sha256']:
            raise ValueError('Original recording hash changed')
        with wave.open(str(path)) as wav:
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, 16000):
                raise ValueError('Expected existing normalized mono PCM16/16kHz')
            duration = wav.getnframes()/16000
        # No cropping: exclude long/short originals with the full transcript.
        if not .3 <= duration <= 5.7:
            excluded['duration-no-cropping'] += 1
            continue
        try:
            tokens = phones(row['text'])
        except ValueError:
            excluded['transcript'] += 1
            continue
        if not 1 <= len(tokens) <= 120:
            excluded['label-length'] += 1
            continue
        speaker = row.get('speaker', row.get('group'))
        holdout = row['source'] == 'ChildMandarin' and int(hashlib.sha256(('ctc-v1:'+speaker).encode()).hexdigest()[:8], 16)%10 == 0
        rows.append({'row': row, 'path': path, 'tokens': tokens, 'validation': holdout})
    rows.sort(key=lambda item: item['row']['sha256'])
    vocab = sorted({t for item in rows if not item['validation'] for t in item['tokens']})
    ids = {token: i+1 for i, token in enumerate(vocab)}
    rows = [item for item in rows if all(t in ids for t in item['tokens'])]
    if sum(item['validation'] for item in rows) < 10:
        raise ValueError('Speaker-held-out phone validation required')
    if a.feature_cache_source:
        features=np.load(a.feature_cache_source/'features.npy',mmap_mode='r')
        cached_labels=np.load(a.feature_cache_source/'labels.npy')
        if (features.shape!=(len(rows),600,40) or features.dtype!=np.float32 or
            cached_labels.shape!=(len(rows),122) or
            json.loads((a.feature_cache_source/'vocabulary.json').read_text())!={'blank':0,'tokens':ids}):
            raise ValueError('Own acoustic cache dimensions/vocabulary changed')
        os.link(a.feature_cache_source/'features.npy',a.output/'features.npy')
    else:
        features = np.lib.format.open_memmap(a.output/'features.npy', mode='w+', dtype=np.float32, shape=(len(rows),600,40))
    labels = np.zeros((len(rows),122), np.int32)
    valid = np.ones(len(rows), bool)
    for i, item in enumerate(rows):
        if a.feature_cache_source:
            with wave.open(str(item['path'])) as wav:
                frames=(wav.getnframes()+3200)//160-2
            n=frames//3
            spec_length=frames
        else:
            pcm = read_audio(item['path'])
            spec, _ = features_and_times(np.pad(pcm, (1600,1600)))
            n = len(spec)//3
            spec_length=len(spec)
        tokens = [ids[t] for t in item['tokens']]
        if spec_length > 600 or n < len(tokens)+sum(x==y for x,y in zip(tokens,tokens[1:])):
            valid[i] = False
            excluded['CTC-alignment-length'] += 1
            continue
        if not a.feature_cache_source:
            features[i] = 0
            features[i,:n*3] = spec[:n*3]
        labels[i,:2] = len(tokens), n
        labels[i,2:2+len(tokens)] = tokens
        if i%250 == 0:
            if not a.feature_cache_source:features.flush()
            print(json.dumps({'phase':'original-phone-features','completed':i+1,'total':len(rows)}), flush=True)
    if a.feature_cache_source:
        if not np.array_equal(labels,cached_labels):
            raise ValueError('Own cache full transcript labels/alignment changed')
    else:features.flush()
    np.save(a.output/'labels.npy', labels)
    folds = np.asarray([item['validation'] for item in rows], bool)
    train_idx, val_idx = np.flatnonzero(valid & ~folds), np.flatnonzero(valid & folds)
    # Prevent later wake fine-tuning from using phone-validation speakers.
    heldout_speakers = {item['row'].get('speaker',item['row'].get('group')) for item in rows if item['validation']}
    bg = []
    for row in manifest:
        if row.get('source') in {'ChildMandarin','PolyAI-MInDS14-zh-CN'} and row.get('speaker',row.get('group')) not in heldout_speakers:
            path = (a.manifest.parent/row['path']).resolve()
            bg.append({**row,'path':str(path)})
    (a.output/'wake-background-train.json').write_text(json.dumps(bg,ensure_ascii=False)+'\n')
    (a.output/'vocabulary.json').write_text(json.dumps({'blank':0,'tokens':ids},ensure_ascii=False,indent=2)+'\n')
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(4)
    tf.config.threading.set_inter_op_parallelism_threads(2)
    from hi_pikoo_model import build
    tf.keras.utils.set_random_seed(2026103101)
    base = build(a.upstream,72,2026103101,a.channels,True)
    encoder = tf.keras.Model(base.input,base.get_layer('ordered_context').input,name='public_phone_encoder')
    x = tf.keras.layers.Reshape((-1,a.channels))(encoder.output)
    logits = tf.keras.layers.Dense(len(ids)+1,name='phone_logits')(x)
    model = tf.keras.Model(encoder.input,logits)
    model.compile(optimizer=tf.keras.optimizers.Adam(.0003,clipnorm=5),loss=ctc_loss)
    if a.resume_ctc:
        model.load_weights(a.resume_ctc)
    rng = np.random.default_rng(2026103101)
    def dataset(indexes, shuffle):
        def batches():
            order = rng.permutation(indexes) if shuffle else indexes
            for begin in range(0,len(order),32):
                index = order[begin:begin+32]
                yield np.asarray(features[index]),labels[index]
        return tf.data.Dataset.from_generator(batches,output_signature=(
            tf.TensorSpec((None,600,40),tf.float32),tf.TensorSpec((None,122),tf.int32))).repeat().prefetch(1)
    class Progress(tf.keras.callbacks.Callback):
        def on_epoch_end(self,epoch,logs=None):
            (a.output/'progress.json').write_text(json.dumps({'epoch':epoch+1,'logs':logs,'household_used':False},indent=2)+'\n')
    checkpoint=a.output/'phone-ctc.weights.h5'
    history=model.fit(dataset(train_idx,True),validation_data=dataset(val_idx,False),epochs=a.epochs,
        steps_per_epoch=math.ceil(len(train_idx)/32),validation_steps=math.ceil(len(val_idx)/32),shuffle=False,
        callbacks=[Progress(),tf.keras.callbacks.CSVLogger(str(a.output/'epochs.csv')),
            tf.keras.callbacks.ModelCheckpoint(str(checkpoint),monitor='val_loss',save_best_only=True,save_weights_only=True),
            tf.keras.callbacks.EarlyStopping(monitor='val_loss',patience=4,start_from_epoch=4)],verbose=2)
    model.load_weights(checkpoint)
    errors, denominator=0.,0
    for x,y in dataset(val_idx,False).take(math.ceil(len(val_idx)/32)):
        output=model(x,training=False)
        decoded,_=tf.nn.ctc_greedy_decoder(tf.transpose(output,[1,0,2]),y[:,1],blank_index=0)
        reference=tf.RaggedTensor.from_tensor(tf.cast(y[:,2:],tf.int64),lengths=y[:,0]).to_sparse()
        errors+=float(tf.reduce_sum(tf.edit_distance(decoded[0],reference,normalize=False)))
        denominator+=int(tf.reduce_sum(y[:,0]))
    encoder.save_weights(a.output/'encoder.weights.h5')
    report={'status':'phone-pretraining-complete-not-wake-acceptance','channels':a.channels,'batch_normalization':True,
        'encoder_hook':'ordered_context.input','initial_projection':96,'local_kernels':[5,9,13],
        'train_clips':len(train_idx),'speaker_heldout_validation_clips':len(val_idx),
        'phone_error_rate':errors/max(1,denominator),'epochs':len(history.history['loss']),
        'source_weights':None,'encoder_sha256':sha(a.output/'encoder.weights.h5'),
        'resumed_own_ctc_sha256':sha(a.resume_ctc) if a.resume_ctc else None,
        'optimizer_reinitialized_for_continuation':bool(a.resume_ctc),
        'cache_sha256':sha(a.output/'features.npy'),
        'wake_background_sha256':sha(a.output/'wake-background-train.json'),
        'manifest_sha256':sha(a.manifest),'permission_sha256':sha(a.permission_record),
        'protected_sha256':sha(a.protected_hashes),'excluded':dict(excluded),
        'household_used':False,'official_validation_or_test_used':False,
        'publication':'private restricted derivatives only','no_cropped_transcripts':True}
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    main()
