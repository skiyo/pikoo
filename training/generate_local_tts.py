#!/usr/bin/env python3
"""Offline fictional voice synthesis. Never accepts reference/household audio.

Prompt families are split before generation. A voice-design prompt is not a
verified human speaker identity; report this limitation in all evaluations.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import wave

PROFILES = [
    ('train-man', 'train', 'adult', 'A warm adult male with a medium-low conversational Mandarin voice.'),
    ('train-woman', 'train', 'adult', 'An adult woman with a relaxed clear medium-pitch conversational Mandarin voice.'),
    ('train-small-boy', 'train', 'childlike', 'A fictional preschool boy with a light small vocal tract, high clear voice and spontaneous everyday speech.'),
    ('train-school-boy', 'train', 'childlike', 'A fictional early school-age boy with a bright youthful Mandarin voice and quick natural articulation.'),
    ('dev-woman', 'validation', 'adult', 'A mature woman with a husky low gentle voice, slightly measured everyday Mandarin articulation.'),
    ('dev-boy', 'validation', 'childlike', 'A fictional schoolboy with a nasal light high youthful voice, soft conversational articulation and uneven natural timing.'),
    ('dev-man', 'validation', 'adult', 'A young adult male with a clear slightly breathy tenor, quick informal Mandarin rhythm and northern accent.'),
    ('dev-girl', 'validation', 'childlike', 'A fictional primary-school girl with a small bright voice, gentle rising and falling melody and slightly slow natural timing.'),
]


def jobs():
    utterances = [
        ('你好皮酷', 1, 'mandarin-pi2-ku4'),
        ('你好Pikoo', 1, 'mixed-pi1-ku1'),
        ('你好，批枯', 1, 'mixed-pi1-ku1'),
        ('你好Pikoo', 1, 'mixed-pi1-ku1'),
        ('你好皮球', 0, 'non-target'),
        ('你好朋友', 0, 'non-target'),
        ('给我讲一个故事', 0, 'non-target'),
        ('皮球在哪里', 0, 'non-target'),
        ('你好批枯', 1, 'mixed-pi1-ku1'),
        ('你好披哭', 1, 'mixed-pi1-ku1'),
        ('你好，批枯。', 1, 'mixed-pi1-ku1'),
        ('你好，披哭！', 1, 'mixed-pi1-ku1'),
    ]
    rows=[]
    for profile_index,(profile,split,style,prompt) in enumerate(PROFILES):
        for index,(text,label,pronunciation) in enumerate(utterances):
            instruction=prompt+' This is an invented voice, not an imitation of a real person. Read only the supplied text.'
            if pronunciation=='mixed-pi1-ku1':
                instruction+=' Say 你好 in Mandarin, followed by PEE-koo, /pi: ku:/, two clear level syllables. Do not say pee-go or pie-co.'
                if 'Pikoo' not in text:instruction+=' The name characters are pronounced pī kū, both first tones. Read the exact Chinese characters.'
            if index==3:instruction+=' Slightly fast connected everyday speech.'
            rows.append(dict(profile=profile,split=split,group='qwen-design:'+profile,
                speaker='qwen-design:'+profile,voice=profile,text=text,label=label,
                pronunciation=pronunciation,synthetic_style=style,instruction=instruction,
                seed=2026101700+(profile_index*8+index if index<8 else 10000+profile_index*100+index),source='Qwen3-TTS-synthetic-local',
                synthetic=True,real_child=False,reference_audio_used=False,
                source_terms='https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign',
                identity_scope='prompt-family; not a verified fixed voice or real speaker'))
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--limit',type=int,default=96)
    a=p.parse_args()
    if not 1<=a.limit<=96:raise ValueError('Bound synthesis to 1..96 utterances')
    # Prevent an optional library from fetching any weights or tokenizer files.
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    os.umask(0o077)
    import mlx.core as mx
    import numpy as np
    from mlx_audio.tts.utils import load_model
    from generate_google import resample
    mx.set_cache_limit(128*1024*1024)
    model=load_model(str(a.model.resolve()))
    a.output.mkdir(parents=True,exist_ok=True);audio=a.output/'audio';audio.mkdir(exist_ok=True)
    rows=[]
    for job in jobs()[:a.limit]:
        identity={**job,'generator':'local-voicedesign-v9-1','weights':a.model.name}
        digest=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
        path=audio/(digest+'.wav');metadata=path.with_suffix('.json')
        if metadata.exists():
            row=json.loads(metadata.read_text())
            if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('Cached synthetic hash mismatch')
        else:
            mx.random.seed(job['seed']);started=time.monotonic()
            outputs=list(model.generate_voice_design(text=job['text'],instruct=job['instruction'],language='auto',
                max_tokens=180,temperature=.7,verbose=False,stream=False))
            if len(outputs)!=1:raise ValueError('Unexpected generated output count')
            part=outputs[0];pcm=np.asarray(part.audio,dtype=np.float32)
            if not .3<=len(pcm)/part.sample_rate<=12:raise ValueError('Unexpected synthetic duration')
            pcm=np.clip(np.rint(resample(pcm*32767,part.sample_rate)),-32768,32767).astype('<i2')
            with wave.open(str(path),'wb') as w:w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(pcm.tobytes())
            row={**identity,'path':str(path.relative_to(a.output)), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                 'seconds':len(pcm)/16000,'elapsed_seconds':round(time.monotonic()-started,2),'label_review':'required'}
            metadata.write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n')
        rows.append(row)
        (a.output/'manifest.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'completed':len(rows),'total':a.limit,'split':job['split'],'label':job['label'],'pronunciation':job['pronunciation']}),flush=True)
        mx.clear_cache()


if __name__=='__main__':main()
