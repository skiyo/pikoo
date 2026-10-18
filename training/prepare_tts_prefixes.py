#!/usr/bin/env python3
"""Matched-voice incomplete targets from reviewed fictional synthesis only.

Use conservative pre-voicing cuts, then independently screen every derivative.
This never generates positive labels or reads household/acceptance recordings.
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


def boundaries(path):
    import parselmouth
    sound=parselmouth.Sound(str(path))
    pitch=sound.to_pitch(time_step=.01,pitch_floor=60,pitch_ceiling=800)
    f=pitch.selected_array['frequency'];times=pitch.xs();voiced=np.flatnonzero(f>0)
    groups=np.split(voiced,np.flatnonzero(np.diff(voiced)>3)+1)
    groups=[g for g in groups if len(g)>=5]
    if len(groups) not in (3,4):raise ValueError('Uncertain isolated-word alignment')
    if any(not .05<=times[g[-1]]-times[g[0]]<=.8 for g in groups[-2:]):
        raise ValueError('Uncertain name syllables')
    return [float(times[g[0]]-.12) for g in groups[-2:]]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--protected-hashes',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();os.umask(0o077)
    rows=json.loads(a.manifest.read_text())
    protected=set(json.loads(a.protected_hashes.read_text())['audio_sha256'].values())
    validate(rows,a.manifest.parent,protected)
    (a.output/'audio').mkdir(parents=True,exist_ok=True);result=[];rejected=0
    for row in rows:
        if not row['label'] or row.get('source') not in {'Google-Gemini-TTS-synthetic','Qwen3-TTS-synthetic-local'} or normalize(row.get('text',''))!='你好皮酷':continue
        if not row.get('synthetic') or row.get('real_child') or row.get('reference_audio_used') or row.get('family_inputs_used'):
            raise ValueError('Only fictional reviewed target synthesis is eligible')
        path=(a.manifest.parent/row['path']).resolve()
        with wave.open(str(path)) as w:
            if (w.getnchannels(),w.getsampwidth(),w.getframerate())!=(1,2,16000):raise ValueError('Expected mono PCM16/16kHz')
            pcm=np.frombuffer(w.readframes(w.getnframes()),'<i2')
        try:cuts=boundaries(path)
        except ValueError:rejected+=1;continue
        for cut in cuts:
            end=int(cut*16000)
            if not 4000<=end<=len(pcm)-1600:continue
            identity={'parent_sha256':row['sha256'],'end_sample':end,'method':'conservative-before-last-voicing-v1'}
            name=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
            target=a.output/'audio'/(name+'.wav');clip=pcm[:end].astype(float)
            clip[-160:]*=np.linspace(1,0,160)
            with wave.open(str(target),'wb') as w:
                w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(np.rint(clip).astype('<i2').tobytes())
            result.append({**row,'label':0,'text':'incomplete wake prefix','source':'TTS-matched-incomplete-prefix',
                'parent_source':row['source'],'parent_sha256':row['sha256'],
                'path':str(target.relative_to(a.output)),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
                'hard_negative':True,'augmentation':identity,'label_review':'required; reject if any full target is still audible'})
    (a.output/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    report={'generated':len(result),'alignment_rejected_parents':rejected,'protected_hashes_checked':len(protected),
        'household_inputs':0,'raw_source_only':True,'matched_actual_waveform_not_just_prompt':True,
        'mandatory_content_screen':True}
    (a.output/'preparation-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))


if __name__=='__main__':main()
