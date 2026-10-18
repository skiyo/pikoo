"""Explicit near-phrase supervision; publish only the scalar wake probability.

Ordinary speech and causal prefixes stay non-targets. Full near phrases get
separate training classes, so their shared greeting cannot solve the task.
"""
import math
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


def attach(binary):
    import tensorflow as tf
    last=binary.layers[-1]
    if not isinstance(last,tf.keras.layers.Dense) or last.units!=1:
        raise ValueError('Contrast supervision requires the scalar sequence head')
    if any(np.any(w!=0) for w in last.get_weights()):
        raise ValueError('Contrast initialization requires the zero wake classifier')
    count=len(PHRASES);bias=np.zeros(count,np.float32);bias[1]=math.log(count-1)
    probabilities=tf.keras.layers.Dense(count,activation='softmax',kernel_initializer='zeros',
        bias_initializer=tf.keras.initializers.Constant(bias),name='near_phrase_probability')(last.input)
    training=tf.keras.Model(binary.inputs[0],probabilities)
    x=tf.keras.layers.Reshape((count,1))(probabilities)
    x=tf.keras.layers.Cropping1D((1,count-2))(x)
    inference=tf.keras.Model(binary.inputs[0],tf.keras.layers.Flatten()(x))
    return training,inference
