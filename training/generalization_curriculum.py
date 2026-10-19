"""Preassigned TRAIN/DEVELOPMENT conditions, separate from all sealed tests.

Prompt conditions describe fictional voices, not verified speaker identities.
Both splits are development inputs and cannot be called independent tests.
"""


def jobs():
    conditions=[
        ('soft velvet chest resonance','even conversational phrasing'),
        ('fine brittle head resonance','short careful pauses'),
        ('light woody resonance','quick smooth informal phrasing'),
        ('airy compressed resonance','gentle deliberate syllables'),
        ('clear wiry resonance','slow linked phrasing with long vowels'),
        ('soft gravelly resonance','brief spontaneous uneven phrasing'),
        ('bright squeezed resonance','quiet brisk phrasing with crisp endings'),
        ('smooth muted resonance','lively separated then connected phrasing'),
    ]
    phrases=[('你好 Pikoo',1),('你好，Pikoo',1),('你好批枯',1),('你好，披哭',1),
             ('你好皮克',0),('你好皮',0),('你好皮球',0),('你好皮皮',0)]
    rows=[];profile=0
    for split,offset in [('train',0),('validation',4)]:
        for style,genders in [('adult',['man','woman']),('childlike',['boylike','girllike'])]:
            for gender in genders:
                for resonance,rhythm in conditions[offset:offset+4]:
                    group=f'qwen-generalization-development-v1:{profile}'
                    character=f'invented adult {gender}' if style=='adult' else f'invented small youthful {gender} character'
                    for index,(text,label) in enumerate(phrases):
                        instruction=f'Fictional voice condition: {character}, {resonance}, {rhythm}. Never imitate a real person. Read only the exact supplied phrase with no other speech.'
                        if label:instruction+=' Say Mandarin 你好 followed by PEE-koo, pī kū, two complete first-tone name syllables. Pikoo, 批枯 and 披哭 name the same robot. Do not say ke or drop koo.'
                        rows.append(dict(profile=group,split=split,group=group,speaker=group,voice=group,
                            text=text,label=label,pronunciation='mixed-pi1-ku1' if label else 'non-target',
                            synthetic_style=style,instruction=instruction,seed=2026101997000+profile*32+index,
                            source='Qwen3-TTS-synthetic-local',synthetic=True,real_child=False,
                            reference_audio_used=False,family_inputs_used=False,
                            synthesis_language='auto' if 'Pikoo' in text else 'Chinese',
                            preassigned_usage=split,source_terms='https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign',
                            identity_scope='fictional development prompt condition; not a verified speaker or independent test'))
                    profile+=1
    return rows
