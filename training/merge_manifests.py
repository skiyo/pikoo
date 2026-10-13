#!/usr/bin/env python3
"""Merge local manifests with paths relative to the output; preserve restrictions."""
import argparse,json,os
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('manifests',nargs='+',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();os.umask(0o077)
result=[]
for manifest in a.manifests:
 for row in json.loads(manifest.read_text()):
  row={**row,'path':os.path.relpath((manifest.parent/row['path']).resolve(),a.output.parent.resolve())};result.append(row)
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('Merged clips:',len(result),'Real child clips:',sum(bool(r.get('real_child')) for r in result))
