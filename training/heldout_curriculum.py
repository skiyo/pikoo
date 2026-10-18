"""Fictional test conditions: generate/check labels, score only after freezing.

These conditions are not verified voice identities or real child recordings.
No references, household inputs or deployment-model scores affect the jobs.
"""

def jobs(version="v11"):
    if version not in {"v11","v12","v13","v14"}:raise ValueError("Unknown preassigned held-out revision")
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
    if version=="v12":
        profiles=[
            ('adult','fictional adult male, dry baritone with a gentle northern Mandarin accent and brisk connected phrasing'),
            ('adult','fictional adult male, soft breathy upper tenor with deliberate but casual Mandarin articulation'),
            ('adult','fictional adult female, low rounded contralto with a slightly rough conversational texture'),
            ('adult','fictional adult female, lively forward mid-high timbre with clear natural Mandarin syllables'),
            ('childlike','fictional preschool boylike character, small bright nasal timbre, lively rising-and-falling everyday Mandarin'),
            ('childlike','fictional early-school boylike character, gentle breathy youthful timbre with relaxed connected Mandarin'),
            ('childlike','fictional young boylike character, slightly husky high thin timbre and short emphatic Mandarin syllables'),
            ('childlike','fictional preschool girllike character, airy tiny rounded timbre with curious gently hesitant Mandarin'),
            ('childlike','fictional school-age girllike character, nasal ringing light youthful timbre with quick everyday Mandarin'),
            ('childlike','fictional youthful character, fine soft head-voice timbre with slow clear but informal Mandarin'),
        ]
    if version=="v13":
        profiles=[
            ('adult','fictional adult male, warm sandy middle register, quiet assured Mandarin with a light northeastern rhythm'),
            ('adult','fictional adult male, thin ringing upper register, relaxed slightly quick connected Mandarin'),
            ('adult','fictional adult female, smooth chest register, gentle clipped Mandarin consonants and unhurried delivery'),
            ('adult','fictional adult female, lightly nasal silvery middle register, playful flowing everyday Mandarin'),
            ('childlike','fictional small boylike character, rounded airy light timbre, careful separated Mandarin syllables'),
            ('childlike','fictional young boylike character, fine reedy nasal timbre, quick low-volume connected Mandarin'),
            ('childlike','fictional small boylike character, grainy soft high timbre, curious lilting Mandarin with uneven timing'),
            ('childlike','fictional schoolboylike character, clear forward youthful timbre, firm short Mandarin syllables'),
            ('childlike','fictional small girllike character, tiny flute-like airy timbre, relaxed natural Mandarin rhythm'),
            ('childlike','fictional young girllike character, light rounded nasal timbre, deliberate connected Mandarin'),
            ('childlike','fictional youthful character, slightly rough whispery upper register, lively Mandarin articulation'),
            ('childlike','fictional youthful character, soft bright fine timbre, restrained slow Mandarin with clear consonants'),
        ]
    if version=="v14":
        profiles=[
            ('adult','fictional adult male, rounded mid-low voice, mellow central Mandarin with short gentle pauses'),
            ('adult','fictional adult male, airy high tenor, lively everyday Mandarin with crisp front consonants'),
            ('adult','fictional adult male, slightly creaky bass, soft conversational Mandarin and smooth vowels'),
            ('adult','fictional adult male, dry forward midrange, measured casual Mandarin with clear syllable endings'),
            ('adult','fictional adult female, full low register, easy connected Mandarin with light nasal resonance'),
            ('adult','fictional adult female, fine bright upper register, quiet flowing Mandarin with a southern cadence'),
            ('adult','fictional adult female, lightly textured middle register, curious quick Mandarin with gentle emphasis'),
            ('adult','fictional adult female, airy rounded alto, slow informal Mandarin with precise final vowels'),
            ('childlike','fictional boylike character, tiny clear forward timbre, relaxed uneven Mandarin syllable lengths'),
            ('childlike','fictional boylike character, soft low-volume youthful voice, brisk Mandarin with delicate consonants'),
            ('childlike','fictional boylike character, bright breathy nasal timbre, unhurried playful Mandarin rhythm'),
            ('childlike','fictional boylike character, slightly raspy high register, short lively connected Mandarin'),
            ('childlike','fictional girllike character, fine hollow upper voice, gentle irregular Mandarin phrasing'),
            ('childlike','fictional girllike character, light ringing youthful timbre, clear rapid everyday Mandarin'),
            ('childlike','fictional girllike character, soft rounded breathy timbre, careful conversational Mandarin'),
            ('childlike','fictional youthful character, reedy bright small voice, low-energy flowing Mandarin articulation'),
        ]
    phrases=[('你好皮酷',1,'mandarin-pi2-ku4'),('你好，皮酷',1,'mandarin-pi2-ku4'),
        ('你好批枯',1,'mixed-pi1-ku1'),('你好，披哭',1,'mixed-pi1-ku1')]
    if version=='v12':phrases[2:4]=[('你好Pikoo',1,'mixed-pi1-ku1'),('你好，批枯',1,'mixed-pi1-ku1')]
    if version=='v13':phrases[2:4]=[('你好 Pee Koo',1,'mixed-pi1-ku1'),('你好，批枯',1,'mixed-pi1-ku1')]
    if version=='v14':phrases[2:4]=[('你好 Pikoo',1,'mixed-pi1-ku1'),('你好，批枯',1,'mixed-pi1-ku1')]
    phrases += [(text,0,'non-target') for text in ['你好皮','你好酷酷','你真酷','你好皮球']]
    rows=[]
    for n,(style,description) in enumerate(profiles):
        for index,(text,label,pronunciation) in enumerate(phrases):
            prompt=f'Invented voice: {description}. Do not imitate a real person. Read only the supplied Chinese text exactly, with no extra words.'
            if version=='v12' and pronunciation=='mixed-pi1-ku1':prompt+=' Pikoo is the invented nickname PEE-koo, pī kū, two clear first-tone syllables.'
            if pronunciation=='mixed-pi1-ku1':prompt+=' 批枯 and 披哭 are pronounced pī kū, both first tones, two clear syllables.'
            if version=='v13' and 'Pee Koo' in text:prompt+=' Say 你好 in Mandarin followed by the invented English nickname PEE-koo, /pi: ku:/, two complete clear syllables.'
            if version=='v14' and 'Pikoo' in text:prompt+=' Say 你好 in Mandarin followed by the English invented name Pikoo, pronounced PEE-koo, /pi: ku:/, both syllables complete. Do not translate the name or substitute another word.'
            group=f'qwen-heldout-{version}:{n}'
            rows.append(dict(profile=group,split='test',group=group,speaker=group,voice=group,
                text=text,label=label,pronunciation=pronunciation,synthetic_style=style,instruction=prompt,
                seed=({'v11':2026101810000,'v12':2026101880000,'v13':2026101900000,'v14':2026101916000}[version])+n*32+index,source='Qwen3-TTS-synthetic-local',
                synthetic=True,real_child=False,reference_audio_used=False,family_inputs_used=False,
                frozen_holdout=True,source_terms='https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign',
                identity_scope='preassigned synthetic test condition, not a verified voice identity'))
            if version=='v13' and 'Pee Koo' in text:rows[-1]['synthesis_language']='auto'
            if version=='v14' and 'Pikoo' in text:rows[-1]['synthesis_language']='auto'
    return rows
