#!/usr/bin/env python3
"""Level the last two voiced regions of reviewed isolated Google wake speech.

PSOLA prosody augmentation, not a new native English or real child recording.
Only exact isolated target phrases are eligible. Parent identities keep splits.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import wave
import numpy as np
from prepare_voice_variants import validate
from review_google_corpus import normalize


def level(source,destination):
    with wave.open(str(source)) as header:
        if (header.getnchannels(),header.getsampwidth(),header.getframerate())!=(1,2,16000):
            raise ValueError('Expected mono 16kHz PCM16 input')
    import parselmouth
    from parselmouth.praat import call
    sound=parselmouth.Sound(str(source))
    pitch=sound.to_pitch(time_step=.01,pitch_floor=65,pitch_ceiling=650)
    f=pitch.selected_array['frequency'];t=pitch.xs();voiced=np.flatnonzero(f>0)
    if len(voiced)<15:raise ValueError('Too little voiced speech')
    groups=np.split(voiced,np.flatnonzero(np.diff(voiced)>3)+1)
    groups=[g for g in groups if len(g)>=5]
    if not 3<=len(groups)<=5:raise ValueError('Uncertain syllable alignment')
    last=groups[-2:]
    if any(not .04<=t[g[-1]]-t[g[0]]<=.7 for g in last):raise ValueError('Uncertain final syllable duration')
    if not .15<=t[last[-1][-1]]-t[last[0][0]]<=1.5:raise ValueError('Uncertain name duration')
    boundary=float(t[last[0][0]]-.015)
    target=float(np.clip(np.percentile(f[voiced],75),90,600))
    manipulation=call(sound,'To Manipulation',.01,65,650)
    tier=call(manipulation,'Extract pitch tier');call(tier,'Remove points between',0,sound.duration)
    for index in voiced:call(tier,'Add point',float(t[index]),target if t[index]>=boundary else float(f[index]))
    call([tier,manipulation],'Replace pitch tier');output=call(manipulation,'Get resynthesis (overlap-add)')
    pcm=np.clip(np.rint(output.values[0]*32767),-32768,32767).astype('<i2')
    if abs(len(pcm)/sound.sampling_frequency-sound.duration)>.002:raise ValueError('Resynthesis changed duration')
    with wave.open(str(destination),'wb') as w:
        w.setparams((1,2,int(sound.sampling_frequency),0,'NONE','not compressed'));w.writeframes(pcm.tobytes())
    return {'method':'Praat-PSOLA-level-last-two-voiced-regions-v1','name_start_seconds':boundary,'target_hz':target,
            'last_syllable_start_seconds':float(t[last[-1][0]]),'voiced_regions':len(groups),
            'syllable_alignment':'heuristic; content review required; not native English ground truth'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--protected-hashes',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--prefix-output',type=Path,help='Optional incomplete-target negatives, separately reviewed before use')
    a=p.parse_args();os.umask(0o077)
    rows=json.loads(a.manifest.read_text());protected=set(json.loads(a.protected_hashes.read_text())['audio_sha256'].values())
    validate(rows,a.manifest.parent,protected)
    a.output.mkdir(parents=True,exist_ok=True);audio=a.output/'audio';audio.mkdir(exist_ok=True);result=[];rejected=[];prefixes=[]
    if a.prefix_output:(a.prefix_output/'audio').mkdir(parents=True,exist_ok=True)
    for row in rows:
        if not row['label'] or row.get('source')!='Google-Gemini-TTS-synthetic' or normalize(row.get('text',''))!='你好皮酷':continue
        identity={'parent':row['sha256'],'method':'Praat-PSOLA-level-last-two-voiced-regions-v1'}
        name=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest();path=audio/(name+'.wav')
        try:details=level((a.manifest.parent/row['path']).resolve(),path)
        except ValueError as e:rejected.append({'parent_sha256':row['sha256'],'reason':str(e)});continue
        result.append({**row,'path':str(path.relative_to(a.output)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'parent_sha256':row['sha256'],'source':'Google-TTS-level-tone-synthetic','pronunciation':'mixed-pi1-ku1',
            'synthetic':True,'real_child':False,'text':'你好批枯','augmentation':details,
            'label_review':'required; prosody derivative not a fresh native utterance'})
        if a.prefix_output:
            with wave.open(str((a.manifest.parent/row['path']).resolve())) as w:
                rate=w.getframerate();pcm=np.frombuffer(w.readframes(w.getnframes()),'<i2')
            cuts=[details['name_start_seconds']-.02]
            if details['voiced_regions']<=4:cuts.append(details['last_syllable_start_seconds']-.08)
            for cut in cuts:
                end=int(cut*rate)
                if not .25<=end/rate<len(pcm)/rate-.1:continue
                identity={'parent':row['sha256'],'end_sample':end,'kind':'incomplete-before-final-syllable-v1'}
                key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest();out=a.prefix_output/'audio'/(key+'.wav')
                with wave.open(str(out),'wb') as w:w.setparams((1,2,rate,0,'NONE','not compressed'));w.writeframes(pcm[:end].tobytes())
                prefixes.append({**row,'path':str(out.relative_to(a.prefix_output)),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),
                    'parent_sha256':row['sha256'],'label':0,'text':'incomplete wake prefix','source':'Google-TTS-incomplete-prefix',
                    'hard_negative':True,'synthetic':True,'real_child':False,'augmentation':identity,'label_review':'required; reject if ASR still hears full target'})
    (a.output/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    (a.output/'preparation-report.json').write_text(json.dumps({'generated':len(result),'rejected':rejected,
        'household_inputs':0,'native_English_or_child_recordings':0},ensure_ascii=False,indent=2)+'\n')
    if a.prefix_output:(a.prefix_output/'manifest.json').write_text(json.dumps(prefixes,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'generated':len(result),'rejected':len(rejected)},ensure_ascii=False))


if __name__=='__main__':main()
