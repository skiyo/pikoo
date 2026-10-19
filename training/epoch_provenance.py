"""Bind saved epoch weights to their completed run without changing reports.

This index contains hashes/epoch numbers only. It never reads recordings or
converts a development checkpoint into independent-test evidence.
"""
import hashlib
import json
from pathlib import Path
import re


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(run):
    run=Path(run);report=run/'report.json';history=run/'training-history.json'
    metadata=json.loads(report.read_text());epochs=int(metadata['epochs'])
    if metadata.get('export_only') or epochs<1 or len(json.loads(history.read_text())['loss'])!=epochs:
        raise ValueError('Epoch provenance requires a completed training run')
    entries={}
    for path in sorted((run/'epochs').glob('epoch-*.weights.h5')):
        match=re.fullmatch(r'epoch-(\d+)\.weights\.h5',path.name)
        if not match or not 1<=int(match[1])<=epochs:raise ValueError('Checkpoint outside completed epoch range')
        entries[path.name]={'epoch':int(match[1]),'sha256':sha(path)}
    if set(e['epoch'] for e in entries.values())!=set(range(1,epochs+1)):
        raise ValueError('Missing completed epoch checkpoints')
    result={'report_sha256':sha(report),'history_sha256':sha(history),'epochs':entries}
    output=run/'epoch-provenance.json'
    if output.exists():
        if json.loads(output.read_text())!=result:raise ValueError('Existing epoch provenance changed')
    else:
        with output.open('x') as out:out.write(json.dumps(result,indent=2)+'\n')
    return result


def resolve(checkpoint):
    checkpoint=Path(checkpoint)
    if checkpoint.parent.name!='epochs':raise ValueError('Expected the original epoch directory')
    run=checkpoint.parent.parent;report=run/'report.json';index=run/'epoch-provenance.json'
    data=json.loads(index.read_text());entry=data['epochs'].get(checkpoint.name)
    if data['report_sha256']!=sha(report) or data['history_sha256']!=sha(run/'training-history.json'):
        raise ValueError('Epoch parent metadata changed')
    if not entry or entry['sha256']!=sha(checkpoint):raise ValueError('Epoch checkpoint hash changed')
    return report,{'epoch':entry['epoch'],'index_sha256':sha(index)}
