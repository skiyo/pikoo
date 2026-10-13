#!/usr/bin/env python3
"""Build aligned wake positives, hard negatives and a frozen holdout plan locally.
Synthetic roles are never labeled as real children. Existing child splits remain.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import wave
import numpy as np

TRAIN=['Eddy (中文（中国大陆）)','Flo (中文（中国大陆）)',
       'Grandma (中文（中国大陆）)','Grandpa (中文（中国大陆）)',
       'Reed (中文（中国大陆）)',
       'Tingting (中文（中国大陆）)','Meijia']
VALIDATION=['Sandy (中文（中国大陆）)']
TEST=['Shelley (中文（中国大陆）)','Rocko (中文（中国大陆）)']
TARGETS=['你好皮酷','你好，皮酷','你好。皮酷']
NEGATIVES=['你好','皮酷','你好皮','酷酷','你好皮球','你好皮皮','你好小酷',
    '你好，酷酷','你好皮卡丘','皮酷你好','你好朋友','你好小朋友',
    '我们去公园玩吧','给我讲个故事','你真酷','别哭了','你好哥哥',
    '请把积木收起来','这个球是蓝色的','现在几点钟','你可以帮我吗','小兔子在睡觉']


def read(path):
    with wave.open(str(path)) as w:
        if (w.getnchannels(),w.getsampwidth(),w.getframerate())!=(1,2,16000):raise ValueError('Bad audio format')
        return np.frombuffer(w.readframes(w.getnframes()),'<i2').copy()


def trim(pcm):
    active=np.flatnonzero(np.abs(pcm.astype(np.int32))>max(50,float(np.max(np.abs(pcm.astype(np.int32))))*.015))
    if not len(active):raise ValueError('Empty speech')
    return pcm[max(0,active[0]-800):min(len(pcm),active[-1]+801)]


def write(path,pcm):
    with wave.open(str(path),'wb') as w:
        w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(pcm.astype('<i2').tobytes())


def prepare(output,children,original,challenge):
    output.mkdir(parents=True,exist_ok=True);raw=output/'raw';audio=output/'audio'
    raw.mkdir(exist_ok=True);audio.mkdir(exist_ok=True)
    def synth(job):
        voice,text,rate=job;key=hashlib.sha256(f'{voice}:{text}:{rate}'.encode()).hexdigest()[:24]
        path=raw/(key+'.wav')
        if not path.exists():
            with tempfile.TemporaryDirectory() as tmp:
                src=Path(tmp)/'speech.aiff'
                subprocess.run(['say','-v',voice,'-r',str(rate),'-o',str(src),text],check=True,capture_output=True,timeout=90)
                subprocess.run(['afconvert','-f','WAVE','-d','LEI16@16000','-c','1',str(src),str(path)],check=True,capture_output=True,timeout=30)
        return job,trim(read(path))
    plans={**{v:('train',[115,150,195,235]) for v in TRAIN},
           **{v:('validation',[125,175,215]) for v in VALIDATION},
           **{v:('test',[143,183,223]) for v in TEST}}
    jobs=[]
    for voice,(split,rates) in plans.items():
        jobs.extend((voice,text,rate) for text in TARGETS for rate in rates)
        jobs.extend((voice,text,173 if split=='train' else 193 if split=='validation' else 213) for text in NEGATIVES)
        jobs.extend([(voice,'嗯',175),(voice,'讲个故事',175)])
    clips={}
    with ThreadPoolExecutor(max_workers=3) as pool:
        for n,(job,pcm) in enumerate(pool.map(synth,jobs)):
            clips[job]=pcm
            if n%25==0:print('Synthesized',n+1,'/',len(jobs),flush=True)
    rows=[]
    for voice,(split,rates) in plans.items():
        for text in TARGETS:
            for rate in rates:
                target=clips[(voice,text,rate)]
                for context in ['isolated','prefix','suffix']:
                    before=clips[(voice,'嗯',175)] if context=='prefix' else np.empty(0,np.int16)
                    after=clips[(voice,'讲个故事',175)] if context=='suffix' else np.empty(0,np.int16)
                    if len(before):before=np.concatenate([before,np.zeros(1600,np.int16)])
                    pcm=np.concatenate([before,target,np.zeros(1600,np.int16),after])
                    end=len(before)+len(target)
                    key=hashlib.sha256(pcm.tobytes()).hexdigest()
                    path=audio/(key+'.wav');write(path,pcm)
                    rows.append(dict(path=str(path.relative_to(output)),label=1,split=split,
                        speaker=voice,group=voice,voice=voice,text=text,rate=rate,context=context,
                        wake_start_sample=len(before),wake_end_sample=end,source='macOS-aligned-v2',real_child=False))
        for text in NEGATIVES:
            rate=173 if split=='train' else 193 if split=='validation' else 213
            pcm=clips[(voice,text,rate)];key=hashlib.sha256(pcm.tobytes()).hexdigest()
            path=audio/(key+'.wav');write(path,pcm)
            rows.append(dict(path=str(path.relative_to(output)),label=0,split=split,
                speaker=voice,group=voice,voice=voice,text=text,rate=rate,
                source='macOS-aligned-v2',real_child=False))
    def add(manifest,selected):
        for r in json.loads(manifest.read_text()):
            if selected(r):
                row={**r,'path':os.path.relpath((manifest.parent/r['path']).resolve(),output.resolve())}
                rows.append(row)
    add(children,lambda r:True)
    add(original,lambda r:r['split']=='train' and r['voice'] in TRAIN)
    # Previously examined challenge examples are development data, never blind data.
    for r in json.loads(challenge.read_text()):
        if r['voice'] not in TRAIN or r['kind']=='homophone':continue
        if r['kind']=='positive' and '讲个故事' in r['text']:continue
        rows.append(dict(path=os.path.relpath((challenge.parent/r['path']).resolve(),output.resolve()),
            label=int(r['kind']=='positive'),split='train',speaker=r['voice'],group=r['voice'],
            voice=r['voice'],text=r['text'],source='known-self-test-v1-development',real_child=False))
    hashes={};speakers={};deduplicated=[];excluded=[]
    # Some installed locale variants share the same underlying voice. Hold out
    # mainland Rocko entirely, including original training examples, and remove
    # exact cross-split duplicates before freezing the plan.
    for row in sorted(rows,key=lambda r:{'train':0,'validation':1,'test':2}[r['split']]):
        if not row['label'] and not row.get('real_child'):
            row['hard_negative']=any(token in row.get('text','') for token in ['你好','皮酷','酷酷'])
        speaker=row.get('speaker',row.get('voice',row['group']))
        if speaker in speakers and speakers[speaker]!=row['split']:raise ValueError('Speaker leakage')
        speakers[speaker]=row['split']
        digest=hashlib.sha256((output/row['path']).read_bytes()).hexdigest()
        if digest in hashes:
            if hashes[digest]!=row['split']:
                excluded.append({'split':row['split'],'source':row.get('source'),'sha256':digest})
            continue
        hashes[digest]=row['split'];deduplicated.append(row)
    (output/'manifest.json').write_text(json.dumps(deduplicated,ensure_ascii=False,indent=2)+'\n')
    report={'plan_version':'iteration-v2-frozen','speaker_plan':plans,'excluded_cross_split_duplicates':excluded,
        'synthetic_is_not_human_validation':True,'known_challenge_used_for_development':True,
        'blind_test_policy':'No test predictions until candidate chosen using validation',
        'splits':{s:{'positive':sum(r['split']==s and r['label']==1 for r in deduplicated),
                    'negative':sum(r['split']==s and r['label']==0 for r in deduplicated)} for s in ['train','validation','test']}}
    (output/'preparation-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--children',type=Path,required=True);p.add_argument('--original',type=Path,required=True)
    p.add_argument('--challenge',type=Path,required=True);a=p.parse_args();os.umask(0o077)
    prepare(a.output,a.children,a.original,a.challenge)


if __name__=='__main__':main()
