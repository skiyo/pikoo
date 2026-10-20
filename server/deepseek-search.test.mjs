import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {DeepSeekSearchProvider} from './deepseek-search.mjs';
import {familyToolsOptions} from './family-tools.mjs';
import {FrontendRetrievalRuntime} from './node_modules/qwen-audio-agent/server/src/frontend/retrieval/frontend-retrieval-runtime.mjs';
import {FrontendNotesStore} from './node_modules/qwen-audio-agent/server/src/conversation/frontend-notes.mjs';
const json=(body,status=200)=>new Response(JSON.stringify(body),{status});
test('Search sends one bounded request and maps native citations without leaking provider metadata',async()=>{
 let calls=0;
 const provider=new DeepSeekSearchProvider({apiKey:'test-secret',fetchImpl:async(url,options)=>{
  calls++;assert.equal(url,'https://api.deepseek.com/v1/tools/search');assert.equal(options.redirect,'error');
  assert.equal(options.headers.Authorization,'Bearer test-secret');
  assert.deepEqual(JSON.parse(options.body),{query:'小猫 中文',count:8,need_content:false});
  return json({results:[{title:'官方资料',url:'https://example.org/cat',summary:'摘要',snippet:'短摘要',date:'2026-10-20T00:00:00Z',site_name:'示例',authority:4,content:'do not expose'},
   {title:'duplicate',url:'https://example.org/cat'}, {title:'unsafe',url:'file:///etc/passwd'}]});
 }});
 const runtime=new FrontendRetrievalRuntime({searchProvider:provider});
 const result=await runtime.search('小猫 中文',{limit:99});
 assert.equal(calls,1);assert.equal(result.results.length,1);assert.equal(result.results[0].snippet,'摘要');
 assert.equal(result.citations[0].published_at,'2026-10-20T00:00:00Z');
 assert(!JSON.stringify(result).includes('test-secret'));assert(!JSON.stringify(result).includes('authority'));
});
test('Search validates Unicode length before I/O and allows empty results',async()=>{
 let calls=0;const p=new DeepSeekSearchProvider({apiKey:'x',fetchImpl:async()=>{calls++;return json({results:[]});}});
 for(const q of ['', '   ', '你'.repeat(129),null])await assert.rejects(p.search(q),{code:'deepseek_invalid_query'});
 assert.equal(calls,0);assert.deepEqual(await p.search('😀'.repeat(128)),{results:[]});assert.equal(calls,1);
 await assert.rejects(new DeepSeekSearchProvider({apiKey:''}).search('cat'),{code:'deepseek_not_configured'});
 assert.equal(familyToolsOptions({}).webSearchProvider.isConfigured(),false);
});
test('Search classifies HTTP and malformed responses without retries or remote error-body leakage',async()=>{
 for(const [status,code] of [[400,'invalid_query'],[401,'authentication'],[402,'insufficient_balance'],[403,'permission'],[429,'rate_limited'],[500,'unavailable'],[302,'request_rejected']]){
  let n=0;const p=new DeepSeekSearchProvider({apiKey:'secret',fetchImpl:async()=>{n++;return json({error:'secret remote detail'},status);}});
  await assert.rejects(p.search('cat'),{code:'deepseek_'+code,message:'deepseek_'+code});assert.equal(n,1);
 }
 for(const response of [()=>json({}),()=>new Response('invalid'),()=>new Response('x'.repeat(262145))]){
  const p=new DeepSeekSearchProvider({apiKey:'x',fetchImpl:async()=>response()});
  await assert.rejects(p.search('cat'),e=>['deepseek_invalid_response','deepseek_response_too_large'].includes(e.code));
 }
});
test('Search deadline covers the response body and explicit cancellation',async()=>{
 const keep=setTimeout(()=>{},1000);
 try{
  const fetchImpl=async(_,o)=>{await new Promise((resolve,reject)=>o.signal.addEventListener('abort',()=>reject(Error('private transport detail')),{once:true}));};
  await assert.rejects(new DeepSeekSearchProvider({apiKey:'x',fetchImpl,timeoutMs:15}).search('cat'),{code:'deepseek_timeout'});
  const stalledBody=async(_,o)=>new Response(new ReadableStream({start(c){o.signal.addEventListener('abort',()=>c.error(Error('body stalled')),{once:true});}}));
  await assert.rejects(new DeepSeekSearchProvider({apiKey:'x',fetchImpl:stalledBody,timeoutMs:15}).search('cat'),{code:'deepseek_timeout'});
  const controller=new AbortController();const result=new DeepSeekSearchProvider({apiKey:'x',fetchImpl}).search('cat',{signal:controller.signal});
  controller.abort();await assert.rejects(result,{code:'deepseek_cancelled'});
 }finally{clearTimeout(keep);}
});
test('URL reader rejects private addresses and notes survive reopen with owner isolation and ambiguity',async t=>{
 const {urlFetcher}=familyToolsOptions({});
 await assert.rejects(urlFetcher.fetch('http://127.0.0.1/private'),{code:'private_network_forbidden'});
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'pikoo-notes-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
 const filePath=path.join(dir,'notes.json');let s=new FrontendNotesStore({filePath});
 s.add('family',{list:'购物清单',items:['牛奶','鸡蛋']});s.add('family',{list:'周末清单',items:['画笔']});
 s=new FrontendNotesStore({filePath});assert.equal(s.show('family','购物清单').items.length,2);
 assert.equal(s.lists('another').length,0);assert.equal(s.show('family','清单').status,'ambiguous');
 s.remove('family',{list:'购物清单',items:['鸡蛋']});s.clear('family','周末清单');s.drop('family','周末清单');
 assert.equal(new FrontendNotesStore({filePath}).show('family','购物清单').items.length,1);
});
