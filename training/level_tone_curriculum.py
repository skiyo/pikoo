"""TRAIN-only first-tone nickname coverage, independent of frozen test jobs."""


def jobs():
    profiles=[
        ('adult','fictional adult man, clear conversational midrange with slightly breathy vowels'),
        ('adult','fictional adult man, dark rounded baritone, relaxed Mandarin with light nasal resonance'),
        ('adult','fictional adult man, bright dry tenor, slightly fast natural northern Mandarin'),
        ('adult','fictional adult man, soft rough low-mid register, measured everyday Mandarin'),
        ('adult','fictional adult woman, warm textured medium register, connected everyday Mandarin'),
        ('adult','fictional adult woman, light clear upper register, quiet precise Mandarin'),
        ('adult','fictional adult woman, slightly husky low voice, quick informal Mandarin'),
        ('adult','fictional adult woman, bright ringing medium-high voice, relaxed careful Mandarin'),
        ('childlike','fictional small boylike voice, fine airy youthful timbre, careful natural Mandarin'),
        ('childlike','fictional young boylike voice, nasal bright small timbre, lively quick Mandarin'),
        ('childlike','fictional small girllike voice, soft rounded youthful timbre, spontaneous gentle Mandarin'),
        ('childlike','fictional young girllike voice, light reedy high timbre, unhurried connected Mandarin'),
    ]
    phrases=[('你好批枯',1),('你好，批枯',1),('你好披哭',1),('你好，披哭',1),
             ('你好皮克',0),('你好皮球',0),('你好皮',0),('你真酷',0)]
    rows=[]
    for n,(style,description) in enumerate(profiles):
        for index,(text,label) in enumerate(phrases):
            group=f'qwen-level-only-train-v1:{n}'
            instruction=f'Invented voice: {description}. Do not imitate a real person. Speak natural Mandarin and read only the exact supplied text, with no extra words.'
            if label:instruction+=' 批枯 and 披哭 are the invented robot name pī kū, both first tones. Keep both syllables complete. Do not substitute ke for kū or omit kū.'
            rows.append(dict(profile=group,split='train',group=group,speaker=group,voice=group,
                text=text,label=label,pronunciation='mixed-pi1-ku1' if label else 'non-target',
                synthetic_style=style,instruction=instruction,seed=2026101960000+n*16+index,
                source='Qwen3-TTS-synthetic-local',synthetic=True,real_child=False,
                reference_audio_used=False,family_inputs_used=False,synthesis_language='Chinese',
                source_terms='https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign',
                identity_scope='preassigned fictional TRAIN prompt family, not a verified voice identity'))
    return rows
