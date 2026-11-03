// SPDX-License-Identifier: Apache-2.0
// Explicit source-only generation. Never records people or scores a model.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),{spawnSync}=require('child_process');
const {cost,reserve,generationCount,existingKeyClient,write,RESERVATION}=require('./hi_pikoo_generate.cjs');
function args(argv){const a={};for(let i=0;i<argv.length;i+=2){if(!argv[i].startsWith('--')||argv[i+1]===undefined)throw Error('Expected --name value');a[argv[i].slice(2)]=argv[i+1];}return a;}
function sourcePreflight(a){
 for(const name of ['python','protocol','policy','model','protected-hashes','native-proof','isolation','output','budget-root','key-file'])if(!a[name])throw Error('Missing --'+name);
 const repair=!!a['source-repair'];let maximum=repair?4:70,limit=Number(a['new-attempt-limit']||maximum);
 if(!Number.isInteger(limit)||limit<1||limit>maximum)throw Error('At most'+maximum+' source attempts per invocation');
 const result=spawnSync(a.python,[path.join(__dirname,'wake_mixed_test_source.py'),
  ...['protocol','policy','model','protected-hashes','native-proof','isolation'].flatMap(k=>['--'+k,a[k]]),
  ...(repair?['--source-repair',a['source-repair']]:[])],{encoding:'utf8',timeout:15000,maxBuffer:1024*1024});
 if(result.status!==0)throw Error('Mixed TEST source preflight failed before credentials: '+String(result.stderr||result.error?.message||'').slice(-1600));
 const plan=JSON.parse(result.stdout);
 if(repair){
  const round=plan.source_repair_round??1;
  if(![1,2].includes(round))throw Error('Only the declared first repair or single follow-up is allowed');
  maximum=round===2?1:4;
  limit=Number(a['new-attempt-limit']||maximum);
  if(limit>maximum)throw Error('At most'+maximum+' source attempts per invocation');
 }
 if(plan.scope!=='synthetic-source-sub-bundle-not-full-TEST'||plan.full_TEST_complete!==false||plan.whole_TEST_slots!==150||plan.synthetic_slots!==70||plan.family_slots_still_required!==80||plan.rows.length!==maximum)throw Error('Full mixed TEST scope missing');
 if(repair&&(plan.source_repair_requests!==maximum||plan.source_repair_active_slots!==4||plan.original70_sources_retained!==true||plan.automatic_retry!==false||
   plan.rows.some(r=>r.source_repair_plan_sha256!==plan.source_repair_plan_sha256||r.generation_request_policy!=='literal-target-response-v2')))throw Error('Source repair proof missing');
 const requested=path.resolve(a.output),root=fs.realpathSync(path.resolve(__dirname,'..'));
 const output=fs.existsSync(requested)?fs.realpathSync(requested):path.join(fs.realpathSync(path.dirname(requested)),path.basename(requested));
 if(output===root||output.startsWith(root+path.sep))throw Error('Audio must remain outside the source repository');
 if(output!==path.join(fs.realpathSync(path.dirname(a.protocol)),repair?'source-repair'+(plan.source_repair_round??1):'synthetic'))throw Error('Use only this TEST protocol\'s private source subdirectory');
 if(fs.realpathSync(a['budget-root'])!==plan.shared_budget_root)throw Error('Must use the protected historical cumulative budget root');
 return {plan,output,limit};
}
async function main(){
 const a=args(process.argv.slice(2)),{plan,output,limit}=sourcePreflight(a);
 const budgetRoot=path.resolve(a['budget-root']),ledgerFile=path.join(budgetRoot,'budget.json');
 // Never initialize a separate ledger or fall back to a fresh $2 allowance.
 if(!fs.existsSync(ledgerFile))throw Error('Existing cumulative budget ledger required');
 const preview=JSON.parse(fs.readFileSync(ledgerFile));
 if(preview.cap_usd!==2||!Array.isArray(preview.entries)||!preview.entries.length)throw Error('Existing cumulative $2 ledger required');
 const generate=existingKeyClient({output,keyFile:a['key-file'],port:Number(a['proxy-port']||7897)});
 process.umask(0o077);
 const lock=path.join(budgetRoot,'generation.lock'),fd=fs.openSync(lock,'wx',0o600);fs.writeSync(fd,String(process.pid));
 try{
  const ledger=JSON.parse(fs.readFileSync(ledgerFile));
  fs.mkdirSync(output,{recursive:true,mode:0o700});
  const planFile=path.join(output,'source-plan.json'),manifestFile=path.join(output,'manifest.json');
  if(fs.existsSync(planFile)&&JSON.stringify(JSON.parse(fs.readFileSync(planFile)))!==JSON.stringify(plan))throw Error('Source plan changed; never overwrite a TEST revision');
  if(!fs.existsSync(planFile))write(planFile,plan);
  const records=fs.existsSync(manifestFile)?JSON.parse(fs.readFileSync(manifestFile)):[];
  let attempts=0;
  const saveStatus=()=>write(path.join(output,'status.json'),{scope:plan.scope,protocol_sha256:plan.protocol_sha256,
   recorded:records.filter(r=>r.status==='recorded').length,failed:records.filter(r=>r.status!=='recorded').length,
   synthetic_slots:70,family_slots_still_required:80,full_TEST_complete:false,model_scored:false,
   cumulative_accounted_or_reserved_USD:ledger.entries.reduce((s,e)=>s+(e.actual_usd??e.reserved_usd),0),updated_at:new Date().toISOString()});
  for(const row of plan.rows){
   const prior=ledger.entries.find(e=>e.id===row.request_id),record=records.find(r=>r.id===row.id);
   if(record){
    if(!prior)throw Error('Source record has no original budget attempt');
    if(record.protocol_sha256!==plan.protocol_sha256||record.speaker!==row.speaker)throw Error('Existing source metadata differs from fixed plan');
    if(record.status==='recorded'){
     const file=path.resolve(output,record.path);
     if(!file.startsWith(output+path.sep))throw Error('Source file escapes its private subdirectory');
     if(crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')!==record.sha256)throw Error('Existing source waveform changed');
    }
    continue;
   }
   if(prior)throw Error('Existing attempt requires manual reconciliation; never retry it');
   if(['.wav','.json'].some(ext=>fs.existsSync(path.join(output,row.request_id+ext))))throw Error('Unregistered prior source files require reconciliation; never reuse them as new');
   if(attempts>=limit)break;
   if(generationCount(ledger)>=1000)throw Error('1000 generation-attempt cap reached');
   reserve(ledger,{id:row.request_id,model:'gpt-realtime-2.1-mini',scope:plan.scope},.2);write(ledgerFile,ledger);
   attempts++;const started=Date.now(),entry=ledger.entries.find(e=>e.id===row.request_id);
   try{
    const saved=await generate([row.request_id,row.voice,row.style,row.text],
     plan.source_repair_requests?{literalTargetOnly:true}:{});
    entry.actual_usd=cost(saved.usage);entry.status='completed';write(ledgerFile,ledger);
    records.push({...saved,...row,status:'recorded',path:saved.file,created_at:saved.created_at,content_review:'pending',admitted_to_training:false});
    write(manifestFile,records);saveStatus();
    if(entry.actual_usd>RESERVATION)throw Error('Request exceeded reservation; stop and audit pricing');
   }catch(error){
    if(!records.some(r=>r.id===row.id)){
     const responseFile=path.join(output,row.request_id+'-response.json');
     if(fs.existsSync(responseFile)){
      const response=JSON.parse(fs.readFileSync(responseFile));entry.actual_usd=cost(response.usage);entry.status='failed-known-usage';
     }else entry.status='usage-unknown-reservation-retained';
     write(ledgerFile,ledger);
     records.push({...row,status:'failed-source-generation',created_at:new Date().toISOString(),failure:String(error.message).replace(/sk-[A-Za-z0-9_-]+/g,'[REDACTED]')});
     write(manifestFile,records);saveStatus();
    }
    throw error;
   }
   await new Promise(resolve=>setTimeout(resolve,Math.max(0,5000-(Date.now()-started))));
  }
  saveStatus();
 }finally{fs.closeSync(fd);fs.unlinkSync(lock);}
}
module.exports={sourcePreflight};
if(require.main===module)main().catch(error=>{console.error(JSON.stringify({status:'stopped',error:String(error.message).replace(/sk-[A-Za-z0-9_-]+/g,'[REDACTED]')}));process.exitCode=1;});
