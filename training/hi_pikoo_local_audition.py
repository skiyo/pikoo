#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Four bounded fictional English voices using already-downloaded Qwen3 TTS.

These are auditions, not verified child data. No household references, cloud
calls, downloads, pitch-shift claims or automatic training admission.
"""
import argparse
from pathlib import Path
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--chinese-description', action='store_true',
                   help='One four-clip comparison after English descriptions failed perceived-age review')
    p.add_argument('--boy-comparison', action='store_true',
                   help='Four fictional boy descriptions after accepted previews sounded feminine')
    a = p.parse_args()
    if a.chinese_description and a.boy_comparison:
        raise ValueError('Choose one distinct audition comparison')
    if not a.model.is_dir():
        raise ValueError('An existing local model is required; never download')
    profiles = [
        ('preschool-boy', 'A fictional four-year-old boy with a genuinely small light child vocal tract, natural high child timbre, softly calling a pet in English with a Mainland Chinese accent.', 'Hi, Pikoo!'),
        ('school-boy', 'A fictional six-year-old boy with a small bright child voice, speaking short natural English with a Mainland Chinese accent, not an adult narrator or cartoon caricature.', 'Hi, Pee Koo!'),
        ('school-girl', 'A fictional six-year-old girl with a light small child voice, everyday natural English, not falsetto or a cartoon character.', 'Hi, Pikoo!'),
        ('child-soft', 'A fictional young schoolboy with a small soft airy child voice, casual connected English greeting with a Mandarin accent, no deliberate syllable pauses.', 'Hi, Pee Koo!'),
    ]
    if a.chinese_description:
        profiles = [
            ('cn-preschool-boy', '这是一个虚构的四岁小男孩的声音。声线稚嫩、细小、明亮，带幼儿自然的奶声和呼吸感，语气天真轻快。不是成年男性、不是青少年、不是卡通尖嗓。用中国孩子自然的英语口音，只读给出的短句。', 'Hi, Pee Koo!'),
            ('cn-school-boy', '虚构的六岁小男孩童声。音色清亮、稚嫩，声道短小，尚未变声，发音清楚但有自然的儿童韵律。像小朋友轻轻叫自己的宠物，使用自然的中国口音英语，只读正文。', 'Hi, Pikoo!'),
            ('cn-preschool-girl', '虚构的五岁小女孩童声，幼儿园小朋友稚嫩明亮的奶声，自然开心地呼唤宠物。避免成熟的成年女声和夸张卡通声。只读正文，名字的声音是皮库。', 'Hi, Pee Koo!'),
            ('cn-phonetic-child', '虚构的五岁小男孩，声音清脆稚嫩，有小孩子自然轻软的奶声和口语节奏。正常音量轻快连读，只读给定的三个音节，不要逐字拉长。', '嗨，批枯！'),
        ]
    if a.boy_comparison:
        profiles = [
            ('boy-nasal', '一个虚构的六岁小男孩的童声，尚未变声，轻而稚嫩，带一点男孩子日常讲话的鼻腔共鸣和微微沙哑感，音调不要过分尖细。不是成年男性，不是成熟青少年，也不是女童。像在家轻快地叫小宠物，用自然中国口音英语，只读正文。', 'Hi, Pee Koo!'),
            ('boy-soft', '虚构的五岁幼儿男孩声音，稚气、松软、带一点小男孩口语里的气声和含糊感，发音仍完整。中高音区但不尖细，不用女孩甜嗓，不用成年男声和卡通嗓音。只读给定英文短句。', 'Hi, Pikoo!'),
            ('boy-playful', '一个虚构的七岁小男孩，未变声的小男童音色，稍低一些但仍细小、稚嫩，鼻音轻微、语气活泼，有男孩子自然说话的粗糙感。正常音量叫宠物，不逐音节念，只读英语正文。', 'Hi, Pee Koo!'),
            ('boy-mandarin', '虚构的五岁小男孩，轻软稚嫩的男童声，稍带鼻音和气声，真实自然的幼儿口语感觉，不是成年男、不像女孩，也不是少年变声后的声音。轻快连读给定短句。', '嗨，批枯！'),
        ]
    rows = []
    for i, (name, prompt, text) in enumerate(profiles):
        rows.append({'profile': 'hi-piku-'+name, 'split': 'train',
            'group': 'qwen-hi-piku:'+name, 'speaker': 'qwen-hi-piku:'+name,
            'voice': name, 'text': text, 'label': 1, 'pronunciation': 'hi-piku-v1',
            'synthetic_style': 'childlike-requested-not-verified',
            'instruction': prompt+' Invent a new voice, not an imitation of any person. Read the supplied text only.',
            'seed': (2026103120 if a.boy_comparison else 2026103110 if a.chinese_description else 2026103100)+i, 'source': 'Qwen3-TTS-hi-piku-synthetic-local',
            'synthetic': True, 'real_child': False, 'reference_audio_used': False,
            'family_inputs_used': False, 'synthesis_language': 'Chinese' if text.startswith('嗨') else 'English',
            'admitted_to_training': False,
            'identity_scope': 'prompt family; neither verified fixed voice nor real child',
            'source_terms': 'https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign'})
    import generate_local_tts as generator
    generator.jobs = lambda *args: rows
    sys.argv = ['generate_local_tts.py', '--model', str(a.model),
                '--output', str(a.output), '--limit', '4']
    generator.main()


if __name__ == '__main__':
    main()
