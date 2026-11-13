#!/usr/bin/env python3
# Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
"""Check tracked publication artifacts, model integrity and Markdown links.

This technical check neither grants model/data rights nor certifies hardware.
Use a redacted full-history secret scanner in addition to this check.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

REVIEWED_WEIGHTS={'models/hi-pikoo/hi_pikoo.tflite','models/hi-pikoo/checkpoint.weights.h5'}
AUDIO={'.wav','.pcm','.aiff','.mp3','.m4a','.flac'}
SECRETS=[
    ('private_key',re.compile(rb'(?m)^\s*-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')),
    ('openai_key',re.compile(rb'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{40,}')),
    ('github_token',re.compile(rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})')),
    ('huggingface_token',re.compile(rb'\bhf_[A-Za-z0-9]{30,}')),
]

def check_file(name,data):
    p=Path(name);issues=[]
    def issue(kind):issues.append({'file':name,'kind':kind})
    if (p.suffix.lower() in AUDIO or name.endswith('.nvs.bin') or p.name in ('factory-full.bin','before-full.bin')
        or p.name in ('USER.md','MEMORY.md') or p.name.startswith('.env') and p.name!='.env.example'
        or any(part in ('node_modules','managed_components','__pycache__','private') for part in p.parts)):
        issue('private_or_generated_artifact')
    if (p.suffix=='.tflite' or name.endswith('.weights.h5')) and name not in REVIEWED_WEIGHTS:issue('unreviewed_weights')
    for kind,pattern in SECRETS:
        if pattern.search(data):issue(kind)
    if name.startswith('examples/') and p.suffix=='.json':
        try:
            def visit(value):
                if isinstance(value,dict):
                    for key,item in value.items():
                        if key in ('api_key','password','token','proxy_basic') and (not isinstance(item,str) or item and not re.fullmatch(r'YOUR_[A-Z0-9_]+',item)):issue('nonplaceholder_example_secret')
                        visit(item)
                elif isinstance(value,list):
                    for item in value:visit(item)
            visit(json.loads(data))
        except (ValueError,UnicodeError):issue('invalid_example_json')
    return issues

def check_model(root):
    folder=root/'models/hi-pikoo';issues=[]
    policy=json.loads((folder/'wake-policy.json').read_text())
    model=folder/'hi_pikoo.tflite'
    if not model.is_file() or hashlib.sha256(model.read_bytes()).hexdigest()!=policy['model_sha256']:
        issues.append({'file':'models/hi-pikoo/hi_pikoo.tflite','kind':'policy_hash_mismatch'})
    listed=set()
    for line in (folder/'SHA256SUMS').read_text().splitlines():
        expected,name=line.split('  ',1);p=folder/name
        if Path(name).name!=name or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:
            issues.append({'file':'models/hi-pikoo/'+name,'kind':'checksum_mismatch'})
        listed.add(name)
    if not {'hi_pikoo.tflite','checkpoint.weights.h5','LICENSE.md','ATTRIBUTION.md','MODEL_CARD.md','MODEL_CARD.zh-CN.md','model-config.json','wake-policy.json','distribution-status.json'}.issubset(listed):
        issues.append({'file':'models/hi-pikoo/SHA256SUMS','kind':'incomplete_model_checksums'})
    return issues

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);args=ap.parse_args();root=args.root.resolve()
    files=subprocess.check_output(['git','ls-files','-z'],cwd=root).decode().split('\0')[:-1];issues=[]
    for name in files:
        p=root/name
        if not p.is_file():issues.append({'file':name,'kind':'missing_tracked_file'});continue
        data=p.read_bytes();issues.extend(check_file(name,data))
        if p.suffix=='.md':
            for link in re.findall(r'\]\(([^)]+)\)',data.decode(errors='replace')):
                link=link.split(' "')[0].strip('<>');target=link.split('#')[0]
                if target and not re.match(r'^[A-Za-z][\w+.-]*:',target) and not (p.parent/target).exists():issues.append({'file':name,'kind':'broken_local_link'})
    issues.extend(check_model(root))
    status=json.loads((root/'models/hi-pikoo/distribution-status.json').read_text())
    print(json.dumps({'tracked_files':len(files),'technical_publication_check':'failed' if issues else 'passed','issues':issues,'model_distribution_status':status['status'],'board_acceptance':'separate review required'},ensure_ascii=False))
    return bool(issues)
if __name__=='__main__':raise SystemExit(main())
