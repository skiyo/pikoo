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


def jobs(contrasts=False,child_focus=False,phonetic_spelling=False):
    contrasts=contrasts or child_focus
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
    if contrasts:
        # Additional TRAIN-only near phrases; no household input or held-out
        # waveform mining. Keep each prompt family in its preassigned split.
        utterances=utterances[:4]+[(text,0,'non-target') for text in (
            '你好皮','你好','你好皮皮','你真酷','你好皮球','你好比酷',
            '你好朋友','你好屁股','皮酷','给我讲一个故事','你好派酷','你好皮克')]
    rows=[]
    for profile_index,(profile,split,style,prompt) in enumerate(PROFILES):
        if contrasts and split!='train':continue
        if child_focus and style!='childlike':continue
        for index,(text,label,pronunciation) in enumerate(utterances):
            if phonetic_spelling and 'Pikoo' in text:text=text.replace('Pikoo','批枯')
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
            if contrasts:rows[-1]['seed']=(2026101850 if child_focus else 2026101800)+profile_index*100+index
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--limit',type=int,default=96)
    p.add_argument('--contrasts',action='store_true',help='Additional train-only incomplete and near-phrase negatives, with synthetic target controls')
    p.add_argument('--child-focus',action='store_true',help='Train-only fictional childlike prompt families; implies contrasts; never real child speech')
    p.add_argument('--phonetic-spelling',action='store_true',help='Constrain mixed-name syllables with Chinese first-tone homophones and explicit Chinese synthesis')
    p.add_argument('--broad',action='store_true',help='36 preassigned fictional voice conditions; 24 train / 12 validation; at most 288 utterances')
    p.add_argument('--heldout',action='store_true',help='Preassigned fictional TEST utterances; generate and score only after a deployment candidate is frozen')
    p.add_argument('--hard-contrasts',action='store_true',help='96 fresh TRAIN-only complete targets and near phrases; preserve broad training prompt groups')
    p.add_argument('--level-contrasts',action='store_true',help='96 TRAIN-only first-tone targets and matched negatives; eight adult and four fictional childlike conditions')
    p.add_argument('--child-level-contrasts',action='store_true',help='320 TRAIN-only first-tone clips; 32 fictional childlike and eight adult conditions; no references')
    p.add_argument('--generalization-contrasts',action='store_true',help='256 preassigned TRAIN/development clips; no independent-test or household input')
    p.add_argument('--clean-development',action='store_true',help='160 fresh preassigned fictional DEVELOPMENT clips for content-audited mixed-name coverage; never a sealed test')
    p.add_argument('--code-switch-spelling',choices=['brand','phonetic','english'],default='brand',help='Explicit sound spelling and optional English synthesis language; retain original curriculum')
    p.add_argument('--code-switch-split',choices=['train','validation'],default='train',help='Explicit preassigned split for code-switch curriculum')
    p.add_argument('--code-switch-contrasts',action='store_true',help='TRAIN-only literal English nickname with near phrases; automatic language')
    p.add_argument('--heldout-version',choices=['v11','v12','v13','v14','v15','v16','v17'],default='v11',help='Explicit independent test revision; V15 onward are first-tone-only; never rescore a consumed test as fresh')
    a=p.parse_args()
    if a.clean_development and any([a.generalization_contrasts,a.heldout,a.broad,a.hard_contrasts,a.child_focus,a.contrasts,a.level_contrasts,a.child_level_contrasts,a.code_switch_contrasts,a.phonetic_spelling]):raise ValueError('Choose content-clean DEVELOPMENT independently')
    if a.generalization_contrasts and any([a.heldout,a.broad,a.hard_contrasts,a.child_focus,a.contrasts,a.level_contrasts,a.child_level_contrasts,a.code_switch_contrasts]):raise ValueError('Choose the generalization TRAIN/development curriculum independently')
    if a.child_level_contrasts and any([a.heldout,a.broad,a.hard_contrasts,a.child_focus,a.contrasts,a.level_contrasts,a.code_switch_contrasts]):raise ValueError('Choose the child-level TRAIN curriculum independently')
    if a.level_contrasts and any([a.heldout,a.broad,a.hard_contrasts,a.child_focus,a.contrasts,a.code_switch_contrasts]):raise ValueError('Choose the TRAIN-only level curriculum independently')
    if a.code_switch_split!='train' and not a.code_switch_contrasts:raise ValueError('Code-switch split requires explicit curriculum')
    if a.code_switch_contrasts and (a.heldout or a.broad or a.hard_contrasts or a.child_focus or a.contrasts):raise ValueError('Choose one explicit curriculum')
    if a.heldout_version!='v11' and not a.heldout:raise ValueError('Test revision requires --heldout')
    if not 1<=a.limit<=(160 if a.clean_development else 256 if a.generalization_contrasts else 320 if a.child_level_contrasts else 288 if a.broad else 256 if a.heldout and a.heldout_version in {'v16','v17'} else 128 if a.heldout and a.heldout_version in {'v14','v15'} else 96):raise ValueError('Synthesis exceeds the selected bounded curriculum')
    if a.broad and (a.child_focus or a.contrasts):raise ValueError('Choose broad or focused curriculum')
    if a.heldout and (a.broad or a.child_focus or a.contrasts):raise ValueError('Held-out curriculum cannot be mixed with development jobs')
    if a.hard_contrasts and (a.heldout or a.broad or a.child_focus or a.contrasts):raise ValueError('Choose one explicit curriculum')
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
    rejected_path=a.output/'rejected-items.json'
    rejected=json.loads(rejected_path.read_text()) if rejected_path.exists() else {}
    if a.clean_development:
        from clean_development_curriculum import jobs as clean_development_jobs
        selected=clean_development_jobs()[:a.limit]
    elif a.generalization_contrasts:
        from generalization_curriculum import jobs as generalization_jobs
        selected=generalization_jobs()[:a.limit]
    elif a.child_level_contrasts:
        from child_level_curriculum import jobs as child_level_jobs
        selected=child_level_jobs()[:a.limit]
    elif a.level_contrasts:
        from level_tone_curriculum import jobs as level_jobs
        selected=level_jobs()[:a.limit]
    elif a.code_switch_contrasts:
        from broad_curriculum import code_switch_jobs
        selected=code_switch_jobs(a.code_switch_split,a.code_switch_spelling)[:a.limit]
    elif a.hard_contrasts:
        from broad_curriculum import hard_contrast_jobs
        selected=hard_contrast_jobs()[:a.limit]
    elif a.heldout:
        from heldout_curriculum import jobs as heldout_jobs
        selected=heldout_jobs(a.heldout_version)[:a.limit]
    elif a.broad:
        from broad_curriculum import jobs as broad_jobs
        selected=broad_jobs()[:a.limit]
    else:selected=jobs(a.contrasts,a.child_focus,a.phonetic_spelling)[:a.limit]
    for attempted,job in enumerate(selected,1):
        identity={**job,'generator':'local-voicedesign-content-clean-development-v2' if a.clean_development else 'local-voicedesign-generalization-development-v1' if a.generalization_contrasts else 'local-voicedesign-child-level-TRAIN-v1' if a.child_level_contrasts else 'local-voicedesign-level-only-TRAIN-v1' if a.level_contrasts else 'local-voicedesign-v11-code-switch' if a.code_switch_contrasts else 'local-voicedesign-v11-hard-contrasts' if a.hard_contrasts else f'local-voicedesign-{a.heldout_version}-heldout' if a.heldout else 'local-voicedesign-v10-broad' if a.broad else 'local-voicedesign-v10-child-phonetic' if a.child_focus else 'local-voicedesign-v10-contrast' if a.contrasts else 'local-voicedesign-v9-1','weights':a.model.name}
        language='Chinese' if a.phonetic_spelling or a.broad or a.heldout or a.hard_contrasts else 'auto'
        language=job.get('synthesis_language',language)
        if a.phonetic_spelling or a.broad or a.heldout or a.hard_contrasts:identity['synthesis_language']=language
        digest=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
        if digest in rejected:continue
        path=audio/(digest+'.wav');metadata=path.with_suffix('.json')
        if metadata.exists():
            row=json.loads(metadata.read_text())
            if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('Cached synthetic hash mismatch')
        else:
            mx.random.seed(job['seed']);started=time.monotonic()
            outputs=list(model.generate_voice_design(text=job['text'],instruct=job['instruction'],language=language,
                max_tokens=180,temperature=.7,verbose=False,stream=False))
            reason=None
            if len(outputs)!=1:reason='Unexpected generated output count'
            else:
                part=outputs[0];pcm=np.asarray(part.audio,dtype=np.float32)
                if not .3<=len(pcm)/part.sample_rate<=12:reason='Unexpected synthetic duration'
            if reason:
                rejected[digest]={'seed':job['seed'],'profile':job['profile'],'reason':reason}
                rejected_path.write_text(json.dumps(rejected,indent=2)+'\n')
                print(json.dumps({'attempted':attempted,'rejected':len(rejected),'reason':reason}),flush=True)
                mx.clear_cache();continue
            pcm=np.clip(np.rint(resample(pcm*32767,part.sample_rate)),-32768,32767).astype('<i2')
            with wave.open(str(path),'wb') as w:w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(pcm.tobytes())
            row={**identity,'path':str(path.relative_to(a.output)), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                 'seconds':len(pcm)/16000,'elapsed_seconds':round(time.monotonic()-started,2),'label_review':'required'}
            metadata.write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n')
        rows.append(row)
        temporary=a.output/'manifest.partial.json'
        temporary.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
        temporary.replace(a.output/'manifest.json')
        print(json.dumps({'completed':len(rows),'attempted':attempted,'total':len(selected),'split':job['split'],'label':job['label'],'pronunciation':job['pronunciation']}),flush=True)
        mx.clear_cache()
    (a.output/'generation-status.json').write_text(json.dumps({'generated':len(rows),'rejected':len(rejected),'planned':len(selected),'synthetic_not_real_child_evidence':True},indent=2)+'\n')


if __name__=='__main__':main()
