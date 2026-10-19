"""Broad TRAIN-only first-tone material; no references or household inputs.

Childlike prompts describe fictional characters, not verified child identities.
All conditions/seeds are disjoint from the independent test plans.
"""


def jobs():
    textures=['small clear nasal timbre','light reedy breathy timbre',
              'soft rounded slightly husky timbre','bright thin forward timbre']
    rhythms=['slow curious separated Mandarin','quick connected casual Mandarin',
             'gentle hesitant then fluent Mandarin','animated uneven everyday Mandarin']
    profiles=[('adult',f'invented adult {gender}, {texture}, easy conversational Mandarin')
              for gender in ['male','female'] for texture in textures]
    profiles += [('childlike',f'invented young {gender} character, {texture}, {rhythm}')
                 for gender in ['boylike','girllike'] for texture in textures for rhythm in rhythms]
    phrases=[('你好批枯',1),('你好，批枯',1),('你好披哭',1),('你好，披哭',1),
             ('你好皮克',0),('你好，皮克',0),('你好皮',0),('你好皮球',0)]
    result=[]
    for n,(style,description) in enumerate(profiles):
        group=f'qwen-TRAIN-child-level-v1:{n}'
        for index,(text,label) in enumerate(phrases):
            instruction=f'New fictional training voice: {description}. Do not imitate a real person. Say only the supplied Chinese text, no extra words.'
            if label:instruction+=' The robot name 批枯 / 披哭 is pī kū, both first tones, like PEE-koo. Finish both syllables, not ke or gou.'
            result.append(dict(profile=group,split='train',group=group,speaker=group,voice=group,
                text=text,label=label,pronunciation='mixed-pi1-ku1' if label else 'non-target',
                synthetic_style=style,instruction=instruction,seed=2026101986000+n*32+index,
                source='Qwen3-TTS-synthetic-local',synthetic=True,real_child=False,
                reference_audio_used=False,family_inputs_used=False,synthesis_language='Chinese',
                source_terms='https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign',
                identity_scope='fictional TRAIN prompt condition, not a verified human voice'))
    return result
