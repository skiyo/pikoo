#!/usr/bin/env python3
"""Generate synthetic Mac speech fixtures; does not access any microphone."""
import argparse,json,subprocess,re
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--cases',type=Path,default=Path(__file__).resolve().parents[1]/'testdata/body_voice_cases.json');p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
for n,c in enumerate(json.loads(a.cases.read_text())):
 subprocess.run(['say','-v',c.get('voice','Tingting'),'-o',str(a.out/(str(n)+'.aiff')),c['text']],check=True)
 info=subprocess.check_output(['afinfo',str(a.out/(str(n)+'.aiff'))],text=True)
 sample_bytes=re.search(r'audio bytes:\s*(\d+)',info)
 if not sample_bytes or int(sample_bytes.group(1))==0:raise RuntimeError('Generated speech is empty; check system speech permission and voice installation')
print(a.out)
