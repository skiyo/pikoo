#!/usr/bin/env python3
"""Validate or create a private, versioned Pikoo configuration. Never print secrets."""
import argparse
import base64
import getpass
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

LIMIT = 16384

def endpoint(value, scheme):
    if not isinstance(value, str) or len(value)>2048 or any(ord(c)<=32 or ord(c)>=127 for c in value) or '\\' in value:
        raise ValueError('Invalid service URL')
    try:
        u=urlsplit(value)
        if u.scheme!=scheme or not u.hostname or u.username or u.password or u.fragment or (u.port is not None and not 1<=u.port<=65535):
            raise ValueError('Invalid service URL')
        host=u.hostname
        if ':' not in host and (len(host)>253 or host.startswith('.') or host.endswith('.') or any(not(c.isascii() and (c.isalnum() or c in '.-')) for c in host)):
            raise ValueError('Invalid service hostname')
    except (ValueError,UnicodeError):
        raise ValueError('Invalid service URL') from None
    return u

def validate(c):
    if not isinstance(c,dict) or c.get('version')!=1 or isinstance(c.get('version'),bool):raise ValueError('Expected configuration version 1')
    if len(json.dumps(c,ensure_ascii=False,separators=(',',':')).encode())>LIMIT:raise ValueError('Configuration is too large')
    for section in ('wifi','agent','live','llm','search','network'):
        if section in c and not isinstance(c[section],dict):raise ValueError('Invalid configuration section')
        for key in ('ssid','password','name','language','instructions','protocol','url','api_key','model','voice','extract_url','proxy_url','proxy_basic'):
            if key in c.get(section,{}) and (not isinstance(c[section][key],str) or '\0' in c[section][key]):raise ValueError('Invalid configuration string')
    def bounded(value,maximum,required=True):
        return isinstance(value,str) and '\0' not in value and len(value.encode())<=maximum and (not required or bool(value))
    def secret(value):
        return isinstance(value,str) and (not value or len(value)<=1024 and all(32<ord(ch)<127 for ch in value))
    wifi=c.get('wifi',{})
    if not bounded(wifi.get('ssid'),32) or not bounded(wifi.get('password'),63,False) or wifi['password'] and len(wifi['password'].encode())<8:raise ValueError('Invalid Wi-Fi settings')
    agent=c.get('agent',dict(name='Pikoo',language='en',instructions=''))
    if not bounded(agent.get('name'),64) or not bounded(agent.get('language'),32) or not bounded(agent.get('instructions',''),2048,False):raise ValueError('Invalid agent settings')
    for name,protocols,scheme in [('live',['openai_live'],'wss'),('llm',['openai_responses','openai_chat_completions'],'https')]:
        s=c.get(name,{})
        if s.get('protocol') not in protocols:raise ValueError('Unsupported '+name+' protocol')
        endpoint(s.get('url'),scheme)
        if not secret(s.get('api_key','')) or not bounded(s.get('model'),128):raise ValueError('Invalid '+name+' settings')
    live=c['live']
    if type(live.get('audio_rate',16000)) is not int or live.get('audio_rate',16000) not in (16000,24000):raise ValueError('Invalid PCM rate')
    if not bounded(live.get('voice','marin'),64):raise ValueError('Invalid voice')
    search=c.get('search',{})
    if type(search.get('enabled',False)) is not bool:raise ValueError('Invalid search enabled flag')
    if search.get('enabled',False):
        if search.get('protocol') not in ('tavily','openai_responses'):raise ValueError('Unsupported search protocol')
        u=endpoint(search.get('url'),'https')
        if not secret(search.get('api_key','')) or search['protocol']=='openai_responses' and not bounded(search.get('model'),128):raise ValueError('Invalid search settings')
        if search.get('extract_url'):
            e=endpoint(search['extract_url'],'https')
            if search['protocol']!='tavily' or (e.hostname,e.port or 443)!=(u.hostname,u.port or 443):raise ValueError('Extraction must use the search origin')
    network=c.get('network',{})
    if network.get('proxy_url'):
        p=endpoint(network['proxy_url'],'https')
        if p.path not in ('','/') or p.query:raise ValueError('Proxy URL must be an HTTPS origin')
    if not secret(network.get('proxy_basic','')) or network.get('proxy_basic') and not network.get('proxy_url'):raise ValueError('Invalid proxy settings')
    return c

def prompt_config():
    c=dict(version=1,wifi=dict(ssid=input('2.4 GHz Wi-Fi SSID: '),password=getpass.getpass('Wi-Fi password: ')),agent=dict(name='Pikoo',language=input('Agent language [en; zh-CN for Chinese]: ').strip() or 'en',instructions=''))
    c['live']=dict(protocol='openai_live',url=input('Live WSS endpoint: ').strip(),api_key=getpass.getpass('Live API key: '),model=input('Live model: ').strip(),voice=input('Voice [marin]: ').strip() or 'marin',audio_rate=16000)
    protocol=input('LLM protocol: responses / chat [responses]: ').strip() or 'responses'
    c['llm']=dict(protocol={'responses':'openai_responses','chat':'openai_chat_completions'}.get(protocol,protocol),url=input('LLM HTTPS endpoint: ').strip(),api_key=getpass.getpass('LLM API key: '),model=input('LLM model: ').strip())
    c['search']=dict(enabled=False);c['network']={}
    validate(c);return c

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path);p.add_argument('--init',type=Path);p.add_argument('--dry-run',action='store_true');a=p.parse_args();os.umask(0o077)
    if bool(a.config)==bool(a.init):p.error('choose --config to validate or --init to create a private configuration')
    if a.init:
        c=prompt_config();fd=os.open(a.init,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f:json.dump(c,f,ensure_ascii=False,indent=2);f.write('\n')
        print('Private configuration saved. No USB or provider calls were made.')
    else:
        validate(json.loads(a.config.read_text()));print('Configuration is valid. No values displayed; no USB or provider calls were made.')
if __name__=='__main__':
    try:main()
    except (ValueError,OSError,TypeError) as e:raise SystemExit(str(e))
