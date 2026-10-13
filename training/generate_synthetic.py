#!/usr/bin/env python3
"""Local macOS speech synthesis for an experimental corpus. No network calls.
Generated audio stays ignored/private. This is NOT child-voice validation.
"""
import argparse, hashlib, json, subprocess, tempfile
from pathlib import Path

NEGATIVES = [
    '你好皮球','你好皮皮','你好小酷','你好小智','你好朋友','你好苹果',
    '你好','皮酷','小皮酷','皮球在哪里','这条皮裤很好看','你好皮卡丘',
    '你真酷','不要哭','我喜欢这只小狗','给我讲一个故事','今天星期几','我们去公园玩吧',
    '爸爸妈妈回来了','我想听恐龙的故事','现在几点钟','请你停一下','我还没有说完',
    '一加一等于几','这是什么颜色','我们吃饭吧','外面正在下雨','小兔子蹦蹦跳跳',
    '明天我想去动物园','你可以帮我吗','谢谢你再见','别说话了','哥哥和弟弟一起玩',
    '请打开窗户','这个球是蓝色的','早上好','晚上好','晚安做个好梦',
]
VOICES = [
    ('Eddy (中文（中国大陆）)','train'),('Flo (中文（中国大陆）)','train'),
    ('Grandma (中文（中国大陆）)','train'),('Grandpa (中文（中国大陆）)','train'),
    ('Reed (中文（中国大陆）)','train'),('Rocko (中文（中国大陆）)','train'),
    ('Sandy (中文（中国大陆）)','validation'),('Shelley (中文（中国大陆）)','test'),
]
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path(__file__).parent/'data/synthetic');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True); manifest=[]
    for voice,split in VOICES:
        samples=[('你好皮酷',1,r) for r in [125,155,185,215,245]] + [(t,0,165 if i%2 else 205) for i,t in enumerate(NEGATIVES)]
        for text,label,rate in samples:
            key=hashlib.sha256(f'{voice}:{rate}:{text}'.encode()).hexdigest()[:20]
            path=a.output/f'{key}.wav'
            if not path.exists():
                with tempfile.TemporaryDirectory() as d:
                    src=Path(d)/'speech.aiff'
                    subprocess.run(['say','-v',voice,'-r',str(rate),'-o',str(src),text],check=True,capture_output=True)
                    subprocess.run(['afconvert','-f','WAVE','-d','LEI16@16000','-c','1',str(src),str(path)],check=True,capture_output=True)
            manifest.append(dict(path=path.name,label=label,split=split,group=key,voice=voice,text=text,rate=rate,source='macOS-local-synthetic'))
        print(f'{split}: completed {voice}',flush=True)
    (a.output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(f'{len(manifest)} clips; held-out synthesis voices are not held-out humans',flush=True)
if __name__=='__main__':main()
