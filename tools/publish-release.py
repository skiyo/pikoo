#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Publish a checked release using the repository-scoped Actions token."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def api(path,method='GET',data=None,upload=None):
    url=path if path.startswith('https://uploads.github.com/') else 'https://api.github.com/repos/'+os.environ['GITHUB_REPOSITORY']+'/'+path
    headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'pikoo-release'}
    payload=upload
    if data is not None:payload=json.dumps(data).encode();headers['Content-Type']='application/json'
    if upload is not None:headers['Content-Type']='application/octet-stream'
    with urllib.request.urlopen(urllib.request.Request(url,data=payload,headers=headers,method=method),timeout=120) as response:
        raw=response.read();return json.loads(raw) if raw else None
def version():
    value=json.loads((ROOT/'release-plan.json').read_text())['version']
    if value!=(ROOT/'VERSION').read_text().strip() or not all(x.isdigit() for x in value.split('.')) or len(value.split('.'))!=3:raise ValueError('Release plan and VERSION differ')
    return value
def wait_checks():
    deadline=time.monotonic()+1200
    while time.monotonic()<deadline:
        runs=api('actions/runs?head_sha='+os.environ['GITHUB_SHA']+'&per_page=50')['workflow_runs']
        selected=[]
        for name in ('Software checks','Public repository audit'):
            matches=[r for r in runs if r['name']==name and r['event']=='push']
            selected.append(max(matches,key=lambda r:r['id']) if matches else None)
        if all(r and r['status']=='completed' for r in selected):
            if any(r['conclusion']!='success' for r in selected):raise ValueError('Required checks failed')
            print('Software and public repository checks passed.');return
        time.sleep(15)
    raise TimeoutError('Required checks did not complete')
def prepare():
    v=version();out=ROOT/'dist'
    shutil.copy2(ROOT/'firmware/build-dualeye/pikoo.bin',out/f'hi-pikoo-esp32s3-app-{v}.bin')
    manifest=json.loads((out/'release-manifest.json').read_text())
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    assert manifest['source_commit']==head and manifest['version']==v and not manifest['nvs_included']
    assert manifest['firmware_sha256']==digest(out/f'hi-pikoo-esp32s3-app-{v}.bin')
    for archive in out.glob('*.zip'):
        with zipfile.ZipFile(archive) as z:
            names=z.namelist();assert len(names)==len(set(names))
            for n in names:
                p=Path(n)
                if p.is_absolute() or '..' in p.parts or p.suffix in ('.wav','.pcm','.aiff','.jsonl') or p.name.startswith('.env') and p.name!='.env.example' or n.endswith('.nvs.bin'):raise ValueError('Private or unsafe archive member')
            assert z.testzip() is None
            for line in z.read('SHA256SUMS').decode().splitlines():
                expected,name=line.split('  ',1);assert hashlib.sha256(z.read(name)).hexdigest()==expected
    manifest['model_publication_status']=json.loads((ROOT/'models/hi-pikoo/distribution-status.json').read_text())['status']
    (out/'release-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (out/'SHA256SUMS').write_text(''.join(digest(p)+'  '+p.name+'\n' for p in sorted(out.iterdir()) if p.is_file() and p.name!='SHA256SUMS'))
    print('Archives, source identity, model hashes and application image verified.')
def cleanup():
    if not json.loads((ROOT/'release-plan.json').read_text()).get('cleanup_merged_branches'):return
    branches=api('branches?per_page=100')
    for b in branches:
        if not b['name'].startswith('codex/') or b.get('protected'):continue
        sha=b['commit']['sha']
        if subprocess.run(['git','merge-base','--is-ancestor',sha,'HEAD'],cwd=ROOT).returncode:continue
        ref='git/refs/heads/'+urllib.parse.quote(b['name'],safe='/')
        current=api(ref)
        if current['object']['sha']!=sha:raise ValueError('Development branch moved; refusing deletion')
        api(ref,'DELETE');print('Removed merged branch:',b['name'])
def publish():
    v=version();tag='v'+v;head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();out=ROOT/'dist'
    try:release=api('releases/tags/'+tag)
    except urllib.error.HTTPError as e:
        if e.code!=404:raise
        release=api('releases','POST',{'tag_name':tag,'target_commitish':head,'name':'Pikoo '+v,'body':(ROOT/'docs/releases'/f'{v}.md').read_text(),'draft':True,'prerelease':False})
    if not release['draft']:
        print('Release already published; preserving its tag and assets.');cleanup();return
    if release.get('target_commitish') not in (head,'main'):
        for asset in api('releases/'+str(release['id'])+'/assets?per_page=100'):
            api('releases/assets/'+str(asset['id']),'DELETE')
        release=api('releases/'+str(release['id']),'PATCH',{'target_commitish':head,'body':(ROOT/'docs/releases'/f'{v}.md').read_text()})
    existing={a['name']:a for a in api('releases/'+str(release['id'])+'/assets?per_page=100')}
    for path in sorted(out.iterdir()):
        if not path.is_file():continue
        checksum='sha256:'+digest(path)
        if path.name in existing:
            if existing[path.name].get('digest')==checksum:continue
            api('releases/assets/'+str(existing[path.name]['id']),'DELETE')
        if not release['draft']:raise ValueError('Refusing to add to a published release')
        url=release['upload_url'].split('{')[0]+'?name='+urllib.parse.quote(path.name)
        uploaded=api(url,'POST',upload=path.read_bytes())
        if uploaded.get('digest')!=checksum or uploaded['size']!=path.stat().st_size:raise ValueError('Uploaded asset integrity mismatch')
        print('Verified uploaded asset:',path.name)
    api('releases/'+str(release['id']),'PATCH',{'draft':False,'make_latest':'true'})
    cleanup();print('Published:',release['html_url'])
if __name__=='__main__':
    action=sys.argv[1];version()
    {'wait':wait_checks,'prepare':prepare,'publish':publish}[action]()
