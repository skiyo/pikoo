#!/usr/bin/env python3
"""Generate a fresh macOS TTS challenge set and compare fixed streaming models.

Synthetic voices are not humans or children. Augmentations of the same utterance
are correlated; report clean results separately from simulated conditions.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import wave
import numpy as np
from evaluate import predict

VOICES=['Tingting (中文（中国大陆）)','Meijia','Eddy (中文（中国大陆）)',
        'Sandy (中文（中国大陆）)','Shelley (中文（中国大陆）)']
POSITIVES=['你好皮酷','你好，皮酷','你好皮酷，讲个故事','嗯，你好皮酷']
NEGATIVES=['你好皮球','你好皮皮','你好皮卡丘','你好小酷','皮酷你好','你好，酷酷',
    '皮球滚到桌子下面了','这双皮鞋有点小','我们等会儿再出去吧','刚刚电视里的声音好大',
    '请把书放到旁边','我的积木不见了','弟弟想喝一杯水','你能数到十吗',
    '现在我们开始做作业','这一道题怎么计算','那只猫正在睡觉','窗外有人在说话',
    '今天晚饭想吃什么','明天上午去超市']
HOMOPHONES=['你好皮裤','你好皮库']
CONDITIONS=['clean','quiet','noise_20db','noise_10db','echo_90ms']


def load(path):
    with wave.open(str(path)) as w:
        if (w.getnchannels(),w.getsampwidth(),w.getframerate())!=(1,2,16000):
            raise ValueError('Expected mono PCM16 16kHz')
        return np.frombuffer(w.readframes(w.getnframes()),'<i2').astype(np.float32)


def modify(pcm,condition,rng):
    x=pcm.copy()
    if condition=='quiet':x*=.25
    elif condition.startswith('noise_'):
        snr=20 if condition=='noise_20db' else 10
        rms=np.sqrt(np.mean(x*x))
        x+=rng.normal(0,rms/(10**(snr/20)),len(x))
    elif condition=='echo_90ms':
        delay=1440
        x=np.pad(x,(0,delay));x[delay:]+=pcm*.25
    return np.clip(x,-32768,32767).astype(np.int16)


def main():
    p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--development-set',action='store_true',help='Known challenge has been used for development; do not call this a blind test')
    a=p.parse_args();os.umask(0o077);a.output.mkdir(parents=True,exist_ok=True)
    audio=a.output/'audio';audio.mkdir(exist_ok=True)
    original=json.loads((Path(__file__).parent/'data/synthetic/manifest.json').read_text())
    used_voices={r['voice'] for r in original};used_keys={(r['voice'],r['text'],r['rate']) for r in original}
    rows=[]
    for voice in VOICES:
        samples=[(t,'positive',r) for t in POSITIVES for r in [130,170,210,250]]
        samples += [(t,'negative',r) for t in NEGATIVES for r in [170,230]]
        samples += [(t,'homophone',r) for t in HOMOPHONES for r in [170,230]]
        for text,kind,rate in samples:
            assert (voice,text,rate) not in used_keys,'Do not reuse original synthesis inputs'
            key=hashlib.sha256(f'self-test-v1:{voice}:{text}:{rate}'.encode()).hexdigest()[:20]
            path=audio/(key+'.wav')
            if not path.exists():
                with tempfile.TemporaryDirectory() as tmp:
                    src=Path(tmp)/'speech.aiff'
                    subprocess.run(['say','-v',voice,'-r',str(rate),'-o',str(src),text],check=True,capture_output=True)
                    subprocess.run(['afconvert','-f','WAVE','-d','LEI16@16000','-c','1',str(src),str(path)],check=True,capture_output=True)
            rows.append(dict(path=str(path.relative_to(a.output)),voice=voice,text=text,kind=kind,
                rate=rate,unseen_voice=voice not in used_voices,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        print('Generated voice',voice,flush=True)
    original_hashes={hashlib.sha256((Path(__file__).parent/'data/synthetic'/r['path']).read_bytes()).hexdigest() for r in original}
    generated_clips=len(rows)
    excluded=[r for r in rows if r['sha256'] in original_hashes]
    rows=[r for r in rows if r['sha256'] not in original_hashes]
    # A synthesizer can quantize close speaking-rate settings to identical audio.
    # Exclude these before scoring; homophones remain diagnostic, not scored negatives.
    (a.output/'excluded-original-duplicates.json').write_text(json.dumps(excluded,ensure_ascii=False,indent=2)+'\n')
    (a.output/'manifest.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    primary=[r['sha256'] for r in rows if r['kind']!='homophone']
    if len(set(primary))!=len(primary):raise ValueError('Duplicate waveforms within primary scored set')
    print('Fresh clips',len(rows),'Excluded old duplicates',len(excluded),flush=True)
    hashes={k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in [('baseline',a.baseline),('candidate',a.candidate)]}
    rng=np.random.default_rng(20261013);details=[]
    for n,row in enumerate(rows):
        pcm=load(a.output/row['path'])
        for condition in CONDITIONS:
            x=modify(pcm,condition,rng)
            scores={k:predict(path,np.pad(x,(16000,16000))) for k,path in [('baseline',a.baseline),('candidate',a.candidate)]}
            details.append({**row,'condition':condition,'seconds':len(x)/16000,'scores':scores,
                           'detected':{k:v>=.9 for k,v in scores.items()}})
        if n%20==0:print('Scored',n+1,'/',len(rows),flush=True)
    summaries={}
    for condition in CONDITIONS:
        group=[r for r in details if r['condition']==condition]
        summary={}
        for model in hashes:
            pos=[r for r in group if r['kind']=='positive'];neg=[r for r in group if r['kind']=='negative']
            summary[model]=dict(positive_clips=len(pos),wake_detected=sum(r['detected'][model] for r in pos),
                negative_clips=len(neg),false_positive_clips=sum(r['detected'][model] for r in neg),
                negative_seconds=sum(r['seconds'] for r in neg))
        summaries[condition]=summary
    voice_summary={}
    for voice in VOICES:
        group=[r for r in details if r['condition']=='clean' and r['voice']==voice]
        voice_summary[voice]={model:{'positive_clips':sum(r['kind']=='positive' for r in group),
            'wake_detected':sum(r['kind']=='positive' and r['detected'][model] for r in group),
            'negative_clips':sum(r['kind']=='negative' for r in group),
            'false_positive_clips':sum(r['kind']=='negative' and r['detected'][model] for r in group)} for model in hashes}
    report=dict(status='development-regression-not-blind' if a.development_set else 'synthetic-challenge-only-not-human-validation',threshold=.9,models=hashes,
        generated_clips=generated_clips,excluded_original_duplicates=len(excluded),base_clips=len(rows),
        unique_synthesis_voices=len(VOICES),unseen_synthesis_voices=None if a.development_set else [v for v in VOICES if v not in used_voices],
        positive_clips=sum(r['kind']=='positive' for r in rows),negative_clips=sum(r['kind']=='negative' for r in rows),
        homophone_clips=sum(r['kind']=='homophone' for r in rows),conditions=summaries,clean_by_voice=voice_summary,
        limitations=['No real adults or child wake phrases','Augmented copies are not independent speakers',
            'Additive noise and single echo are simulations, not microphone/acoustic tests',
            'Homophones are diagnostic and excluded from false-positive pass/fail',
            'Known challenge used for development; not blind evidence' if a.development_set else 'Fixed threshold; models not tuned on this challenge'],details=details)
    for model,path in [('baseline',a.baseline),('candidate',a.candidate)]:
        assert hashlib.sha256(path.read_bytes()).hexdigest()==hashes[model],'Model changed during test'
    (a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='details'},ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
