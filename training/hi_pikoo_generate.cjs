// Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
// Explicit synthetic generation; no microphone, household corpus or model access.
const fs=require('fs'),path=require('path'),http=require('http'),https=require('https'),tls=require('tls'),crypto=require('crypto');
const {createRequire}=require('module');
const req=createRequire(path.join(__dirname,'../server/package.json')); const WebSocket=req('ws');
const MODEL='gpt-realtime-2.1-mini', CAP=2, RESERVATION=.012;
const VOICES={train:['marin','cedar','coral','alloy'],validation:['ash','sage'],test:['ballad','verse']};
let out,key,model=MODEL,proxyPort=7897;
function cost(u){
 if(!u||!Number.isFinite(u.input_tokens)||!Number.isFinite(u.output_tokens))throw Error('Missing usage');
 const i=u.input_token_details,o=u.output_token_details;
 if(!i||!o||![i.text_tokens,i.audio_tokens,o.text_tokens,o.audio_tokens].every(Number.isFinite)||i.audio_tokens!==0)throw Error('Unexpected usage modalities');
 if([u.input_tokens,u.output_tokens,i.text_tokens,o.text_tokens,o.audio_tokens].some(x=>!Number.isInteger(x)||x<0))throw Error('Invalid usage counts');
 if(o.text_tokens+o.audio_tokens!==u.output_tokens||i.text_tokens!==u.input_tokens)throw Error('Unaccounted token types');
 // Reasoning is already included in output text tokens. Ignore cache discount conservatively.
 return (i.text_tokens*.6+o.text_tokens*2.4+o.audio_tokens*20)/1e6;
}
function write(file,value){const tmp=file+'.partial';fs.writeFileSync(tmp,JSON.stringify(value,null,2),{mode:0o600});fs.renameSync(tmp,file);}
function reserve(ledger,entry,holdback=.5){
 if(!ledger.entries.every(x=>Number.isFinite(x.actual_usd??x.reserved_usd)&&(x.actual_usd??x.reserved_usd)>=0))throw Error('Invalid budget ledger');
 const used=ledger.entries.reduce((s,x)=>s+(x.actual_usd??x.reserved_usd),0);
 if(used+RESERVATION+holdback>CAP)throw Error('Budget exhausted; no request sent');
 if(ledger.entries.some(x=>x.id===entry.id))throw Error('Existing reservation requires reconciliation, never retry automatically');
 ledger.entries.push({...entry,status:'reserved',reserved_usd:RESERVATION});return used;
}
function plan(){
 const rows=[];
 const styles=[['adult','standard','Warm everyday adult English.'],['adult','Chinese-accent','Native Mandarin-speaking adult using natural Chinese-accented English.'],['childlike','standard','Fictional youthful playful synthetic English delivery; no imitation of a real person.'],['childlike','Chinese-accent','Fictional Mandarin-speaking young child naturally calling a pet in short Chinese-accented English; no imitation of a real person.'],['childlike','Chinese-accent','Fictional youthful soft casual Chinese-accented English, natural connected speech, no imitation.']];
 const speeds=['Natural connected everyday speed.','A slightly fast connected greeting.','Soft conversational voice, without whispering.','A short natural pause, not syllable-by-syllable reading.'];
 const negs=[['Hi!','Read only Hi. Do not add a name.'],['Pikoo!','The name alone is PEE-koo /piː kuː/. Do not add a greeting.'],['Hi, Piko!','The name is PEE-koh /piː koʊ/, ending in the vowel of go, NOT koo.'],['Hi, Tikoo!','The name is TEE-koo /tiː kuː/, starts with t, not p.'],['Hi, pee!','Say only Hi pee. Stop after pee; do not complete any name.'],['Give me the blue cup.','Read exactly this ordinary sentence.'],['哥哥，我们一起玩吧。','Read exactly this ordinary Mandarin sentence.'],['The puppy is sleeping.','Read exactly this ordinary English sentence.']];
 for(const [split,n] of [['train',700],['validation',150],['test',150]])for(let i=0;i<n;i++){
  const label=i%10<7?1:0,st=styles[Math.floor(i/10)%styles.length],voice=VOICES[split][Math.floor(i/50)%VOICES[split].length];
  let text,phonetic,kind='wake';
  if(label){text=['Hi, Pikoo!','Hi, Pee Koo!','嗨，批枯！'][Math.floor(i/7)%3];phonetic='Say Hi /haɪ/ then PEE-koo /piː kuː/. Preserve both name syllables and final /uː/. The Mandarin spelling 嗨批枯 specifies the same sounds. Do not exaggerate vowel length or insert syllable pauses.';}
  else {const neg=negs[(Math.floor(i/10)*3+i%10-7)%negs.length];[text,phonetic]=neg;kind=['Hi!','Pikoo!','Hi, pee!'].includes(text)?'incomplete':'near-or-ordinary';}
  rows.push({id:split+'-'+String(i).padStart(4,'0'),split,voice,speaker:'openai:'+voice,group:'openai:'+voice,text,label,synthetic_style:st[0],accent:st[1],kind,style:'Read the supplied text exactly once. No introduction, extra words, sound effects or repeated greeting. '+phonetic+' '+st[2]+' '+speeds[Math.floor(i/5)%4],source:'OpenAI-Realtime-synthetic',synthetic:true,real_child:false,family_inputs_used:false,reference_audio_used:false,model:MODEL});
 }
 return rows;
}
function targetPlan(rows,contract){
 const names={'hi-piku-v1':['piku'],'hi-piku-piko-v2':['piku','piko']};
 if(!names[contract.target]||JSON.stringify(contract.accepted_names)!==JSON.stringify(names[contract.target])||contract.declared_before_corpus_training!==true)throw Error('Invalid explicit target contract');
 return rows.map(raw=>{const r={...raw,target_contract:contract.target};
  if(contract.target==='hi-piku-piko-v2'&&/^hi[\s,!.-]+piko[!.]?$/i.test(r.text))Object.assign(r,{label:1,original_label:raw.label,label_change_reason:'explicit pre-training dual-pronunciation contract'});
  return r;
 });
}
function expansionPlan(contract){
 if(contract?.target!=='hi-piku-piko-v2')throw Error('Expansion requires dual target');
 const phrases=[['Hi, Pikoo!',1],['Hi, Piko!',1],['Hi, Pee Koo!',1],['Hi, Piko!',1],
  ['Hi, Tikoo!',0],['Pikoo!',0],['Piko!',0],['Hi!',0],['Hi, pee!',0],['Hi, Tiko!',0]];
 return Array.from({length:100},(_,i)=>{const [text,label]=phrases[i%10],voice=VOICES.train[Math.floor(i/25)],accent=Math.floor(i/10)%2?'Chinese-accent':'standard';
  return {id:'train-expanded-'+String(i).padStart(4,'0'),split:'train',voice,speaker:'openai:'+voice,group:'openai:'+voice,
   text,label,target_contract:contract.target,synthetic_style:'adult',accent,kind:label?'wake':'incomplete-or-confusable',
   recipe:'literal-adult-v4',source:'OpenAI-Realtime-synthetic',synthetic:true,real_child:false,family_inputs_used:false,reference_audio_used:false,model:MODEL,
   style:'Read the user text aloud exactly once without commentary or repetition. '+(accent==='Chinese-accent'?'A natural Mandarin Chinese accent when reading English. ':'Natural English. ')+['Casual connected everyday speech.','Slightly fast natural speech.','Soft everyday speech, without whispering.','A brief natural pause after Hi; no syllable-by-syllable reading.'][Math.floor(i/10)%4]};
 });
}
function validateFrozen(contract,frozen,binary){
 if(!contract||frozen.target!==contract.target||!frozen.candidate_frozen_at||frozen.development_passed!==true)throw Error('Qualified candidate and matching explicit target required before TEST');
 if(contract.target==='hi-piku-piko-v2'&&JSON.stringify(frozen.accepted_names)!==JSON.stringify(contract.accepted_names))throw Error('Frozen target names differ');
 if(!Buffer.isBuffer(binary)||crypto.createHash('sha256').update(binary).digest('hex')!==frozen.model_sha256)throw Error('Frozen model hash mismatch');
}
function tunnel(){return new Promise((resolve,reject)=>{const r=http.request({hostname:'127.0.0.1',port:proxyPort,method:'CONNECT',path:'api.openai.com:443',headers:{Host:'api.openai.com:443'},timeout:15000});r.on('timeout',()=>r.destroy(Error('proxy-connect-timeout')));r.on('error',reject);r.on('connect',(res,socket,head)=>{if(res.statusCode!==200){socket.destroy();return reject(Error('proxy-status-'+res.statusCode));}if(head.length)socket.unshift(head);const s=tls.connect({socket,servername:'api.openai.com',rejectUnauthorized:true});s.once('secureConnect',()=>resolve(s));s.once('error',reject);});r.end();});}
function wav(pcm){const b=Buffer.alloc(44);b.write('RIFF');b.writeUInt32LE(36+pcm.length,4);b.write('WAVEfmt ',8);b.writeUInt32LE(16,16);b.writeUInt16LE(1,20);b.writeUInt16LE(1,22);b.writeUInt32LE(24000,24);b.writeUInt32LE(48000,28);b.writeUInt16LE(2,32);b.writeUInt16LE(16,34);b.write('data',36);b.writeUInt32LE(pcm.length,40);return Buffer.concat([b,pcm]);}
async function generate([name,voice,style,text]){
 const file=path.join(out,name+'.wav'),meta=path.join(out,name+'.json');if(fs.existsSync(file)&&fs.existsSync(meta)){console.log(JSON.stringify({clip:name,cached:true}));return JSON.parse(fs.readFileSync(meta));}
 console.log(JSON.stringify({clip:name,status:'requesting',model}));
 const socket=await tunnel(); const agent=new https.Agent({keepAlive:false}); agent.createConnection=()=>socket;
 return new Promise((resolve,reject)=>{let settled=false,chunks=[],size=0,transcript='',started=false;
 const ws=new WebSocket('wss://api.openai.com/v1/realtime?model='+model,{headers:{Authorization:'Bearer '+key},agent,handshakeTimeout:15000});
 const timer=setTimeout(()=>finish(Error('generation-timeout')),60000);
 function finish(err,result){if(settled)return;settled=true;clearTimeout(timer);ws.terminate();socket.destroy();if(err)reject(err);else resolve(result);}
 ws.on('error',err=>finish(Error('websocket-transport-error '+String(err.message).split(key).join('[REDACTED]'))));ws.on('close',()=>{if(!settled)finish(Error('closed-before-completion'));});
 ws.on('open',()=>ws.send(JSON.stringify({type:'session.update',session:{type:'realtime',model,instructions:style,output_modalities:['audio'],audio:{output:{format:{type:'audio/pcm',rate:24000},voice}},max_output_tokens:512}})));
 ws.on('message',raw=>{try{const e=JSON.parse(raw.toString());if(e.type==='error'){const err={code:e.error?.code,type:e.error?.type,message:String(e.error?.message||'').split(key).join('[REDACTED]')};fs.writeFileSync(path.join(out,name+'-error.json'),JSON.stringify(err,null,2));return finish(Error('API error '+JSON.stringify(err)));}
 if(e.type==='session.updated'&&!started){started=true;ws.send(JSON.stringify({type:'conversation.item.create',item:{type:'message',role:'user',content:[{type:'input_text',text}]}}));ws.send(JSON.stringify({type:'response.create',response:{output_modalities:['audio'],max_output_tokens:512}}));}
 if(e.type==='response.output_audio.delta'){const b=Buffer.from(e.delta,'base64');chunks.push(b);size+=b.length;if(size>48000*10)finish(Error('audio-duration-limit'));}
 if(e.type==='response.output_audio_transcript.delta')transcript+=e.delta;
 if(e.type==='response.done'){
  fs.writeFileSync(path.join(out,name+'-response.json'),JSON.stringify({status:e.response?.status,status_details:e.response?.status_details,usage:e.response?.usage,model:e.response?.model},null,2));
  if(e.response?.status!=='completed'||!size)return finish(Error('response-incomplete-or-empty'));
  const bytes=wav(Buffer.concat(chunks));fs.writeFileSync(file,bytes);const row={file:path.basename(file),model,reported_model:e.response?.model,voice,style:style,text,transcript,seconds:size/48000,usage:e.response?.usage,sha256:crypto.createHash('sha256').update(bytes).digest('hex'),synthetic:true,real_child:false,purpose:'audition-only-not-admitted-to-training',created_at:new Date().toISOString()};fs.writeFileSync(meta,JSON.stringify(row,null,2));console.log(JSON.stringify({clip:name,status:'saved',seconds:row.seconds,transcript,usage:row.usage}));finish(null,row);
 }
 }catch(err){finish(Error('event-processing-error '+String(err.message).split(key).join('[REDACTED]')));}});
 });
}
function args(argv){const a={};for(let i=0;i<argv.length;i+=2){if(!argv[i].startsWith('--')||argv[i+1]===undefined)throw Error('Expected --name value');a[argv[i].slice(2)]=argv[i+1];}return a;}
async function main(){
 const a=args(process.argv.slice(2));if(!a.output||!a['key-file']||!a['audition-root'])throw Error('Required: --output, --key-file, --audition-root');
 const phase=a.phase||'pilot';if(!['pilot','training','development','sealed'].includes(phase))throw Error('Unknown collection phase');
 let contract=null;
 if(a['target-contract']){contract=JSON.parse(fs.readFileSync(a['target-contract'],'utf8'));targetPlan([],contract);}
 if(phase!=='pilot'){
  if(!a['source-review'])throw Error('Source audition evidence is required before expansion');
  const evidence=JSON.parse(fs.readFileSync(a['source-review'],'utf8'));
  if(evidence.clips?.['train-0060']?.pronunciation_piku!=='accepted')throw Error('Adult source audition not accepted');
 }
 if(phase==='sealed'){
  if(!a['frozen-candidate'])throw Error('Frozen candidate required before TEST synthesis');
  const frozen=JSON.parse(fs.readFileSync(a['frozen-candidate'],'utf8'));
  if(!a['candidate-model'])throw Error('Candidate model required before TEST');
  validateFrozen(contract,frozen,fs.readFileSync(a['candidate-model']));
 }
 out=path.resolve(a.output);proxyPort=Number(a['proxy-port']||7897);if(!Number.isInteger(proxyPort)||proxyPort<1||proxyPort>65535)throw Error('Invalid proxy port');
 const env=fs.readFileSync(a['key-file'],'utf8');const line=env.split(/\r?\n/).find(l=>/^\s*(?:export\s+)?OPENAI_API_KEY\s*=/.test(l));if(!line)throw Error('Missing existing API key');key=line.slice(line.indexOf('=')+1).trim().replace(/^['"]|['"]$/g,'');
 process.umask(0o077);fs.mkdirSync(out,{recursive:true,mode:0o700});
 const lock=path.join(out,'generation.lock');const fd=fs.openSync(lock,'wx',0o600);fs.writeSync(fd,String(process.pid));
 try{
 const ledgerFile=path.join(out,'budget.json');let ledger;
 if(fs.existsSync(ledgerFile))ledger=JSON.parse(fs.readFileSync(ledgerFile));else{
  ledger={cap_usd:CAP,reservation_per_request_usd:RESERVATION,price_snapshot:'2026-10-31: text in .60/M, text out 2.40/M incl reasoning, audio out20/M',entries:[]};
  for(const name of ['hi-pikoo-gpt-mini-audition-20261031','hi-pikoo-gpt-mini-default-pronunciation-20261031']){
   const file=path.join(a['audition-root'],name,'manifest.json');
   if(!fs.existsSync(file))throw Error('Prior audition usage missing');
   for(const r of JSON.parse(fs.readFileSync(file)))ledger.entries.push({id:name+'/'+r.file,status:'completed',reserved_usd:0,actual_usd:cost(r.usage)});
  }write(ledgerFile,ledger);
 }
 const recipe=a.recipe||'literal';if(recipe!=='literal')throw Error('Annotated recipe failed content review; only literal synthesis is enabled');
 let planned=plan().map(row=>recipe==='annotated'?row:{...row,recipe:'literal-v2',text:row.label?(row.text.includes('Pee')?'Hi, Pee Koo!':'Hi, Pikoo!'):row.text,style:'Read the user text aloud exactly once, without commentary, repetition, or reading these instructions. '+(row.synthetic_style==='childlike'?'Youthful fictional synthetic delivery. ':'Relaxed adult delivery. ')+(row.accent==='Chinese-accent'?'Natural Mandarin Chinese accent when speaking English. ':'Natural English. ')+'Casual connected speech, normal volume and pace.'});
 if(contract)planned=targetPlan(planned,contract);
 if(phase!=='pilot')for(const row of planned){row.requested_style=row.synthetic_style;row.synthetic_style='adult';row.recipe='literal-adult-v3';row.style='Read the user text aloud exactly once, without commentary or repetition. Natural relaxed adult speech. '+(row.accent==='Chinese-accent'?'A gentle Mandarin Chinese accent when reading English. ':'Natural English. ');}
 if(phase==='training')planned=expansionPlan(contract);
 const planFile=path.join(out,phase==='training'?'generation-plan.training-expansion-v2.json':phase==='sealed'?'generation-plan.sealed.'+contract.target+'.json':phase==='pilot'?'generation-plan.literal-v2.json':'generation-plan.literal-adult-v3.json');
 if(fs.existsSync(planFile)){if(JSON.stringify(JSON.parse(fs.readFileSync(planFile)))!==JSON.stringify(planned))throw Error('Frozen generation plan differs');}else write(planFile,planned);
 const manifestFile=path.join(out,phase==='sealed'?'manifest-test.json':phase==='training'?'manifest-training-expansion.json':'manifest.json');
 let newAttempts=0;let done=fs.existsSync(manifestFile)?JSON.parse(fs.readFileSync(manifestFile)):[];
 const selected=phase==='training'?planned:phase==='pilot'?planned.filter(x=>x.split==='train').slice(0,200):planned.filter(x=>x.split===(phase==='development'?'validation':'test'));
 for(const row of selected){
  if(done.some(x=>x.id===row.id))continue;
  const prior=ledger.entries.find(x=>x.id===row.id); if(prior){if(['failed-known-usage','failed-estimated-charge'].includes(prior.status))continue;throw Error('Unresolved prior attempt; manual reconciliation required');}
  if(newAttempts>=(phase==='pilot'?20:150)){write(path.join(out,'status.json'),{phase:'literal-pilot-awaiting-review',new_attempts:newAttempts,completed:done.length,updated_at:new Date().toISOString()});return;}
  if(ledger.entries.length>=1008)throw Error('1000 generation-attempt cap reached');
  ++newAttempts;reserve(ledger,{id:row.id},phase==='sealed'?.2:.5);write(ledgerFile,ledger);const started=Date.now();
  try{
   const saved=await generate([row.id,row.voice,row.style,row.text]);
   const entry=ledger.entries.find(x=>x.id===row.id);entry.actual_usd=cost(saved.usage);entry.status='completed';write(ledgerFile,ledger);
   const merged={...saved,...row,path:saved.file,model:MODEL,content_review:'pending',pronunciation_review:'pending',admitted_to_training:false};
   done.push(merged);write(manifestFile,done);
   write(path.join(out,'status.json'),{phase:phase+'-generation',completed:selected.filter(x=>done.some(y=>y.id===x.id)).length,total:selected.length,total_retained_files:done.length,estimated_spend_usd:ledger.entries.reduce((s,x)=>s+(x.actual_usd??x.reserved_usd),0),updated_at:new Date().toISOString(),next:'independent content review; no automatic expansion or training'});
   if(entry.actual_usd>RESERVATION)throw Error('Reservation exceeded; stop and audit pricing');
  }catch(err){const entry=ledger.entries.find(x=>x.id===row.id);const responseFile=path.join(out,row.id+'-response.json');
   if(fs.existsSync(responseFile)){const response=JSON.parse(fs.readFileSync(responseFile));entry.actual_usd=cost(response.usage);entry.status='failed-known-usage';entry.failure=response.status_details;write(ledgerFile,ledger);
    if(response.status==='incomplete'&&response.status_details?.reason==='max_output_tokens'){console.log(JSON.stringify({clip:row.id,status:'quarantined-token-limit',charged_usd:entry.actual_usd}));await new Promise(r=>setTimeout(r,Math.max(0,5000-(Date.now()-started))));continue;}}
   if(entry.status==='reserved'){entry.status='usage-unknown-reservation-retained';write(ledgerFile,ledger);}throw err;}
  await new Promise(r=>setTimeout(r,Math.max(0,5000-(Date.now()-started))));
 }
 write(path.join(out,'status.json'),{phase:phase+'-generated-awaiting-independent-review',completed:selected.filter(x=>done.some(y=>y.id===x.id)).length,total:selected.length,total_retained_files:done.length,updated_at:new Date().toISOString(),next:'independent content and pronunciation review; no training admission yet'});
 }finally{fs.closeSync(fd);fs.unlinkSync(lock);}
}
module.exports={cost,reserve,plan,targetPlan,expansionPlan,validateFrozen,RESERVATION};
if(require.main===module)main().catch(err=>{console.error(JSON.stringify({status:'stopped',error:String(err.message).replace(/sk-[A-Za-z0-9_-]+/g,'[REDACTED]')}));process.exitCode=1;});
