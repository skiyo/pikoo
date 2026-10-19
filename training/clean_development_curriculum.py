"""Preassigned content-audited DEVELOPMENT supplement, never a sealed test.

Literal nickname synthesis is fragile. Generate surplus conditions before
content review; exclude disagreements rather than correcting labels. Fictional
childlike voices do not establish real-child performance.
"""


def jobs():
    phrases = [('你好 Pikoo', 1), ('你好，Pikoo', 1),
               ('你好Pikoo。', 1), ('你好，Pikoo！', 1),
               ('你好批枯', 1), ('你好，披哭', 1),
               ('你好皮克', 0), ('你好皮', 0),
               ('你好皮球', 0), ('给我讲一个故事', 0)]
    timbres = [('rounded mellow resonance', 'calm linked syllables'),
               ('fine clear resonance', 'light measured articulation'),
               ('dry soft resonance', 'brisk everyday phrasing'),
               ('airy bright resonance', 'unhurried crisp final vowels')]
    rows = []
    profile = 0
    for style, genders in [('adult', ['man', 'woman']),
                           ('childlike', ['boylike', 'girllike'])]:
        for gender in genders:
            for timbre, rhythm in timbres:
                group = f'qwen-generalization-development-v1:content-v2:{profile}'
                character = (f'invented adult {gender}' if style == 'adult' else
                             f'invented small youthful {gender} animated character')
                for index, (text, label) in enumerate(phrases):
                    instruction = (f'New fictional development condition: {character}, '
                        f'{timbre}, {rhythm}. Never imitate a real person. '
                        'Read only the supplied phrase with no extra words.')
                    if label:
                        instruction += (' Say the Mandarin greeting 你好 followed by '
                            'PEE-koo, pī kū. Both name syllables have level first tones. '
                            'Pikoo, 批枯 and 披哭 are the same robot name. '
                            'Keep the complete final koo vowel; do not say ke.')
                    rows.append(dict(profile=group, split='validation', group=group,
                        speaker=group, voice=group, text=text, label=label,
                        pronunciation='mixed-pi1-ku1' if label else 'non-target',
                        synthetic_style=style, instruction=instruction,
                        seed=2026102025000 + profile * 32 + index,
                        source='Qwen3-TTS-synthetic-local', synthetic=True,
                        real_child=False, reference_audio_used=False,
                        family_inputs_used=False, preassigned_usage='validation',
                        synthesis_language='auto' if 'Pikoo' in text else 'Chinese',
                        source_terms='https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign',
                        identity_scope='preassigned fictional development prompt; not a human speaker or independent test'))
                profile += 1
    return rows
