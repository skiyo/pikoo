#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Package reviewed source, firmware and model without private NVS or corpus data."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile
from device import build_files
from check_wake_policy import validate

ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def copy(a,b):b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(a,b)
def checksums(root):
    (root/'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.relative_to(root).as_posix()}\n' for p in sorted(root.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))
def zip_tree(root,path):
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(root.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(root))
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for n in ('build','model','checkpoint','idf','output'):ap.add_argument('--'+n,type=Path,required=True)
    a=ap.parse_args();version=(ROOT/'VERSION').read_text().strip()
    description=json.loads((a.build/'project_description.json').read_text())
    if description.get('project_version')!=version:raise ValueError('Firmware version differs from VERSION')
    images,_=build_files(a.build)
    policy=ROOT/'models/hi-pikoo/wake-policy.json'
    validate(a.model,json.loads(policy.read_text()))
    generated=(a.build/'esp-idf/main/wake_policy_generated.hpp').read_text()
    if sha(policy) not in generated or sha(a.model) not in generated:raise ValueError('Build does not embed the published model/policy pair')
    a.output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pikoo-release-') as tmp:
        tmp=Path(tmp);firmware=tmp/'firmware';model=tmp/'model';firmware.mkdir();model.mkdir()
        files=subprocess.check_output(['git','ls-files','--cached','--deduplicate'],cwd=ROOT,text=True).splitlines()
        for f in files:
            p=ROOT/f
            if not p.is_file():continue
            if p.suffix in {'.wav','.pcm','.aiff','.jsonl'} or '.env.local' in f or '.nvs.bin' in f:raise ValueError('Private source file in release index')
            copy(p,firmware/f)
        dest=firmware/'firmware/build-dualeye'
        for _,p in images:copy(p,dest/p.relative_to(a.build.resolve()))
        for f in ('flasher_args.json','pikoo-board.json'):copy(a.build/f,dest/f)
        (dest/'project_description.json').write_text(json.dumps({'target':'esp32s3','project_name':'pikoo','project_version':version},indent=2)+'\n')
        for base,name in [(a.idf,'esp-idf'),(ROOT/'firmware/managed_components','components')]:
            for p in base.rglob('*'):
                if p.is_file() and any(p.name.lower().startswith(n) for n in ('license','copying','notice')):
                    if any(t in p.parts for t in ('.git','build','__pycache__')):continue
                    copy(p,firmware/'licenses'/name/p.relative_to(base))
        for p in (ROOT/'models/hi-pikoo').iterdir():
            if p.is_file():copy(p,model/p.name)
        copy(a.model,model/'hi_pikoo.tflite');copy(a.checkpoint,model/'checkpoint.weights.h5')
        copy(ROOT/'LICENSE',model/'SOURCE-CODE-LICENSE');copy(ROOT/'NOTICE',model/'SOURCE-CODE-NOTICE')
        manifest={'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'version':version,'board':'waveshare-dualeye-1.28','idf':'5.5.5','model_sha256':sha(a.model),'policy_sha256':sha(policy),'nvs_included':False,'source_license':'Apache-2.0','model_terms':'models/hi-pikoo/LICENSE.md','firmware_sha256':sha(dest/'pikoo.bin')}
        (firmware/'release-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        for tree in (firmware,model):checksums(tree)
        zip_tree(firmware,a.output/f'hi-pikoo-firmware-{version}.zip');zip_tree(model,a.output/f'hi-pikoo-model-{version}.zip')
        (a.output/'release-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    checksums(a.output)
    print('Packaged source + firmware, model + checkpoint, license texts and SHA256SUMS; no USB or provider calls.')
if __name__=='__main__':main()
