"""Preassigned fictional voice conditions, not verified human identities.

No reference recordings, household inputs, or validation-waveform mining.
Prompt conditions are split before synthesis, and derivatives inherit the split.
"""

def jobs():
    profiles=[]
    adult_train=[
        'adult male, low and rounded, relaxed northern Mandarin',
        'adult male, clear tenor, brisk everyday Mandarin',
        'adult male, slightly nasal and soft, southern Mandarin accent',
        'adult male, textured middle pitch, measured standard Mandarin',
        'adult female, clear bright middle pitch, natural Mandarin',
        'adult female, low warm and a little breathy, casual Mandarin',
        'adult female, resonant and crisp, slightly fast Mandarin',
        'adult female, light soft and slightly nasal, southern Mandarin',
    ]
    adult_dev=[
        'adult male, quiet baritone with a light rasp and flowing Mandarin',
        'adult male, high light tenor with deliberate northern Mandarin syllables',
        'adult female, rich contralto with a dry texture and informal Mandarin',
        'adult female, airy light soprano and gently connected Mandarin',
    ]
    for split,conditions in [('train',adult_train),('validation',adult_dev)]:
        for index,condition in enumerate(conditions):
            profiles.append((split,f'{split}-adult-{index}','adult',condition))
    train_timbres=[
        'small high clear voice, lively but not shouted',
        'light nasal high voice, quiet conversational delivery',
        'thin airy voice, careful everyday articulation',
        'bright rounded voice, quick connected speech',
        'soft slightly husky youthful voice, unhurried articulation',
        'small resonant voice, gentle varied intonation',
        'light breathy youthful voice, slightly hesitant rhythm',
        'clear youthful voice with a soft southern Mandarin accent',
    ]
    dev_timbres=[
        'delicate high voice, soft resonant vowels and flowing rhythm',
        'small dry textured voice, light nasal resonance and short syllables',
        'bright youthful voice, melodic informal rhythm and careful consonants',
        'thin gentle voice, slightly breathy connected conversational syllables',
    ]
    for split,timbres in [('train',train_timbres),('validation',dev_timbres)]:
        for gender in ('boylike','girllike'):
            for index,timbre in enumerate(timbres):
                profiles.append((split,f'{split}-{gender}-{index}','childlike',
                    f'fictional {gender} animated character, {timbre}, standard Mandarin'))
    rows=[]
    for profile_index,(split,profile,style,description) in enumerate(profiles):
        negatives=(['你好皮','你真酷','你好皮球','你好皮皮'] if profile_index%2==0 else
                   ['你好朋友','你好比酷','皮酷','你好皮克'])
        utterances=[('你好皮酷',1,'mandarin-pi2-ku4'),('你好，皮酷',1,'mandarin-pi2-ku4'),
                    ('你好批枯',1,'mixed-pi1-ku1'),('你好，披哭',1,'mixed-pi1-ku1')]
        utterances += [(text,0,'non-target') for text in negatives]
        for index,(text,label,pronunciation) in enumerate(utterances):
            instruction=f'Invented voice: {description}. This is not an imitation of a real person. Read only the supplied Chinese text exactly, without extra words.'
            if pronunciation=='mixed-pi1-ku1':
                instruction+=' 批枯 and 披哭 are pronounced pī kū, both first tones; preserve these exact syllables.'
            rows.append(dict(profile=profile,split=split,group='qwen-broad:'+profile,
                speaker='qwen-broad:'+profile,voice=profile,text=text,label=label,
                pronunciation=pronunciation,synthetic_style=style,instruction=instruction,
                seed=202610180000+profile_index*32+index,source='Qwen3-TTS-synthetic-local',
                synthetic=True,real_child=False,reference_audio_used=False,family_inputs_used=False,
                source_terms='https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign',
                identity_scope='preassigned prompt condition; not a verified fixed voice or real speaker'))
    return rows


def hard_contrast_jobs():
    """Fresh TRAIN synthesis; never imitate a development/test condition."""
    rows=[]
    profiles=[r for r in jobs() if r['split']=='train' and r['text']=='你好皮酷']
    for n,base in enumerate(profiles):
        phrases=[('你好皮酷',1,'mandarin-pi2-ku4'),('你好批枯',1,'mixed-pi1-ku1'),
                 ('你好皮球',0,'non-target'),('你好酷酷' if n%2==0 else '你真酷',0,'non-target')]
        for index,(text,label,pronunciation) in enumerate(phrases):
            instruction=base['instruction']
            if pronunciation=='mixed-pi1-ku1':instruction+=' 批枯 is pī kū, two clear first-tone syllables.'
            rows.append({**base,'text':text,'label':label,'pronunciation':pronunciation,
                'instruction':instruction,'seed':2026101820000+n*32+index,
                'purpose':'train-only fresh near-phrase contrasts; no development waveform or voice imitation'})
    return rows
