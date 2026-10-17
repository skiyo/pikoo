"""Preserve a narrow convolutional network while adding independent channels.

New channels keep their random initialization. Their connections into existing
channels/head start at zero, so the original function is preserved initially.
"""
import numpy as np


def warm_start_wider(target,source):
    if len(target.layers)!=len(source.layers):raise ValueError('Layer structures differ')
    for dst,src in zip(target.layers,source.layers):
        if type(dst).__name__!=type(src).__name__:raise ValueError('Layer types differ')
        old,new=src.get_weights(),dst.get_weights()
        if len(old)!=len(new):raise ValueError('Weight structures differ')
        copied=[]
        for a,b in zip(old,new):
            if a.ndim!=b.ndim or any(x>y for x,y in zip(a.shape,b.shape)):raise ValueError('Only channel widening is supported')
            value=b.copy()
            if a.ndim==4 and type(dst).__name__!='DepthwiseConv2D':
                value[:,:,a.shape[2]:,:a.shape[3]]=0
            elif a.ndim==2:value[a.shape[0]:,:a.shape[1]]=0
            value[tuple(slice(0,n) for n in a.shape)]=a
            copied.append(value)
        dst.set_weights(copied)
