#!/usr/bin/env python3
"""Validate a local ESP-SR binary pack before a diagnostic image is built.

Format reference: the pinned ESP-SR model/pack_model.py. No weights are shipped
here. MultiNet7 requires FST command files as well as acoustic coefficients.
"""
import argparse
import json
import re
import struct
from pathlib import Path


def validate(binary):
    cursor=0;entries=[];models={}
    def number():
        nonlocal cursor
        if cursor+4>len(binary):raise ValueError('Truncated model-pack header')
        value=struct.unpack_from('<I',binary,cursor)[0];cursor+=4;return value
    def name():
        nonlocal cursor
        if cursor+32>len(binary):raise ValueError('Truncated model-pack name')
        raw=binary[cursor:cursor+32];cursor+=32
        try:value=raw.split(b'\0',1)[0].decode('ascii')
        except UnicodeDecodeError:raise ValueError('Invalid model-pack name') from None
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}',value):raise ValueError('Invalid model-pack name')
        return value
    count=number()
    if not 1<=count<=32:raise ValueError('Invalid model count')
    for _ in range(count):
        model=name();files=number()
        if model in models or not 1<=files<=32:raise ValueError('Invalid model file table')
        models[model]=[]
        for _ in range(files):
            filename=name();offset=number();size=number()
            if filename in models[model] or size<1:raise ValueError('Duplicate or empty model file')
            models[model].append(filename);entries.append((offset,size))
    for offset,size in entries:
        if offset<cursor or offset+size>len(binary):raise ValueError('Model file outside packed payload')
    required={'mn7_cn':{'mn7_data','mn7_index','vocab','_MODEL_INFO_'},'fst':{'commands_cn.txt'}}
    for model,files in required.items():
        if not files.issubset(models.get(model,[])):
            raise ValueError('Missing required '+model+' acoustic/dictionary files')
    return {'status':'command-model-pack-valid','bytes':len(binary),'models':models}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('model',type=Path)
    args=parser.parse_args();print(json.dumps(validate(args.model.read_bytes())))
