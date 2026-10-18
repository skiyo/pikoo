"""Fictional test conditions: generate/check labels, score only after freezing.

These conditions are not verified voice identities or real child recordings.
No references, household inputs or deployment-model scores affect the jobs.
"""

def jobs():
    profiles=[
        ('adult','fictional adult male, light nasal tenor, fluent gently connected Mandarin'),
        ('adult','fictional adult male, low mellow voice, precise unhurried Mandarin'),
        ('adult','fictional adult female, warm lower pitch, brisk conversational Mandarin'),
        ('adult','fictional adult female, bright soft soprano, light southern Mandarin accent'),
        ('childlike','fictional boylike character, light airy youthful timbre, slightly hesitant clear Mandarin'),
        ('childlike','fictional boylike character, resonant small voice, fast but careful Mandarin syllables'),
        ('childlike','fictional boylike character, bright nasal high voice, gentle flowing Mandarin'),
        ('childlike','fictional girllike character, soft fine high timbre, short clear Mandarin syllables'),
        ('childlike','fictional girllike character, rounded youthful voice, everyday connected Mandarin'),
        ('childlike','fictional girllike character, light husky small voice, slow relaxed Mandarin'),
    ]
    phrases=[('你好皮酷',1,'mandarin-pi2-ku4'),('你好，皮酷',1,'mandarin-pi2-ku4'),
        ('你好批枯',1,'mixed-pi1-ku1'),('你好，披哭',1,'mixed-pi1-ku1')]
    phrases += [(text,0,'non-target') for text in ['你好皮','你好酷酷','你真酷','你好皮球']]
    rows=[]
    for n,(style,description) in enumerate(profiles):
        for index,(text,label,pronunciation) in enumerate(phrases):
            prompt=f'Invented voice: {description}. Do not imitate a real person. Read only the supplied Chinese text exactly, with no extra words.'
            if pronunciation=='mixed-pi1-ku1':prompt+=' 批枯 and 披哭 are pronounced pī kū, both first tones, two clear syllables.'
            group=f'qwen-heldout-v11:{n}'
            rows.append(dict(profile=group,split='test',group=group,speaker=group,voice=group,
                text=text,label=label,pronunciation=pronunciation,synthetic_style=style,instruction=prompt,
                seed=2026101810000+n*32+index,source='Qwen3-TTS-synthetic-local',
                synthetic=True,real_child=False,reference_audio_used=False,family_inputs_used=False,
                frozen_holdout=True,source_terms='https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign',
                identity_scope='preassigned synthetic test condition, not a verified voice identity'))
    return rows
