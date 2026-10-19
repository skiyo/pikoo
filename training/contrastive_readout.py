"""Explicit near-phrase supervision; publish only the scalar wake probability.

Ordinary speech and causal prefixes stay non-targets. Full near phrases get
separate training classes, so their shared greeting cannot solve the task.
"""
import math
import hashlib
import json
from pathlib import Path
import numpy as np
from review_google_corpus import normalize


PHRASES=['other','wake','你好皮','你好皮球','你好酷酷','你好皮皮','你好皮克',
         '你好屁股','你好比酷','你好派酷','你好朋友','皮酷','你真酷','你好']


def category(row,partial=False):
    if row['label']:return 1
    if partial or row.get('mined_training_prefix') or row.get('causal_end_sample'):return 0
    text=normalize(row.get('text',''))
    return PHRASES.index(text) if text in PHRASES[2:] else 0


def expanded_labels(rows,positive_repeats,negative_repeats,hard_negative_repeats,negative_prefixes):
    """Mirror dataset repetition exactly; no waveform or held-out reads."""
    result={split:[] for split in ['train','validation','test']}
    for row in rows:
        if row.get('evaluation_only') or row.get('frozen_holdout') or str(row.get('source','')).startswith('private-'):
            raise ValueError('Protected audio cannot supervise contrast classes')
        repeats=(positive_repeats if row['label'] else hard_negative_repeats if row.get('hard_negative') else 1 if row.get('real_child') else negative_repeats) if row['split']=='train' else 1
        for n in range(repeats):
            partial=negative_prefixes and not row['label'] and row['split']=='train' and bool(n%2)
            result[row['split']].append(category(row,partial))
    for split in result:
        result[split].extend([0]*(100 if split=='train' else 20))
        result[split]=np.asarray(result[split],np.float32)
    return result


def attach(binary,warm_start=False):
    import tensorflow as tf
    last=binary.layers[-1]
    if not isinstance(last,tf.keras.layers.Dense) or last.units!=1:
        raise ValueError('Contrast supervision requires the scalar sequence head')
    if not warm_start and any(np.any(w!=0) for w in last.get_weights()):
        raise ValueError('Contrast initialization requires the zero wake classifier')
    if warm_start and last.get_config()['activation']!='sigmoid':
        raise ValueError('Warm contrast initialization requires a sigmoid classifier')
    count=len(PHRASES);bias=np.zeros(count,np.float32);bias[1]=math.log(count-1)
    probabilities=tf.keras.layers.Dense(count,activation='softmax',kernel_initializer='zeros',
        bias_initializer=tf.keras.initializers.Constant(bias),name='near_phrase_probability')(last.input)
    training=tf.keras.Model(binary.inputs[0],probabilities)
    if warm_start:
        # Identical non-target logits sum to count-1. Adding log(count-1)
        # to the target logit preserves the original sigmoid probability.
        original_kernel,original_bias=last.get_weights()
        kernel=np.zeros((original_kernel.shape[0],count),np.float32)
        kernel[:,1]=original_kernel[:,0]
        bias[1]+=float(original_bias[0])
        training.get_layer('near_phrase_probability').set_weights([kernel,bias])
    x=tf.keras.layers.Reshape((count,1))(probabilities)
    x=tf.keras.layers.Cropping1D((1,count-2))(x)
    inference=tf.keras.Model(binary.inputs[0],tf.keras.layers.Flatten()(x))
    return training,inference


def resume_readout(training,inference,checkpoint,features,architecture):
    """Resume an explicitly described trained class mapping, not a new head."""
    checkpoint=Path(checkpoint);epoch_proof=None
    if checkpoint.parent.name=='epochs':
        from epoch_provenance import resolve
        metadata,epoch_proof=resolve(checkpoint)
    else:metadata=checkpoint.parent/'report.json'
    report=json.loads(metadata.read_text());readout=report.get('classifier_readout',{})
    if readout.get('type')!='warm-plain-near-phrase' or readout.get('classes')!=PHRASES:
        raise ValueError('Incompatible trained near-phrase class mapping')
    for key,value in architecture.items():
        if report.get(key)!=value:raise ValueError('Trained readout architecture differs: '+key)
    digest=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if not epoch_proof and report.get('checkpoint_weights_sha256',digest)!=digest:
        raise ValueError('Trained checkpoint hash differs from its report')
    # ModelCheckpoint saves the training graph (including optimizer state).
    # Its scalar view shares all classifier/encoder variables with training.
    (training if epoch_proof else inference).load_weights(checkpoint)
    all_probabilities=training(features,training=False).numpy()
    difference=float(np.max(np.abs(inference(features,training=False).numpy()-all_probabilities[:,1:2])))
    if difference>1e-6:raise ValueError('Resumed scalar and class views disagree')
    return {'checkpoint_sha256':digest,'metadata_sha256':hashlib.sha256(metadata.read_bytes()).hexdigest(),
            'source_manifest_sha256':report.get('training_manifest_sha256'),
            'class_order_verified':True,'shared_view_max_difference':difference,
            **({'source_epoch':epoch_proof} if epoch_proof else {})}


def widen_readout(training,inference,checkpoint,features,architecture,binary_builder):
    """Copy every trained class into a wider encoder; verify all probabilities."""
    checkpoint=Path(checkpoint);report=json.loads((checkpoint.parent/'report.json').read_text())
    source={key:report[key] for key in ['filters','first_filters','kernels']}
    if source['kernels']!=architecture['kernels'] or report['feature_config']['window_frames']!=architecture['window_frames']:
        raise ValueError('Wider classifier changes kernels or temporal context')
    if source['filters']>=architecture['filters'] or source['first_filters']>architecture['first_filters']:
        raise ValueError('Wider classifier requires genuinely added channels')
    narrow,narrow_view=attach(binary_builder(source),warm_start=True)
    proof=resume_readout(narrow,narrow_view,checkpoint,features,source)
    from widen import warm_start_wider
    warm_start_wider(training,narrow)
    difference=float(np.max(np.abs(training(features,training=False).numpy()-narrow(features,training=False).numpy())))
    shared=float(np.max(np.abs(inference(features,training=False).numpy()-training(features,training=False).numpy()[:,1:2])))
    if difference>1e-5 or shared>1e-6:raise ValueError('Wider classifier changed trained probabilities')
    return {**proof,'source_filters':source['filters'],'source_first_filters':source['first_filters'],
            'all_class_initial_max_difference':difference,'shared_view_max_difference':shared,
            'new_channels_trainable':True}
