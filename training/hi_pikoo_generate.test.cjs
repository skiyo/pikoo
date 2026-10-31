// SPDX-License-Identifier: Apache-2.0
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {cost,reserve,plan,targetPlan,expansionPlan,validateFrozen,RESERVATION}=require('./hi_pikoo_generate.cjs');
test('reasoning is not charged twice and unaccounted usage fails closed',()=>{
 const u={input_tokens:98,output_tokens:100,input_token_details:{text_tokens:98,audio_tokens:0},output_token_details:{text_tokens:69,audio_tokens:31,reasoning_tokens:54}};
 assert.ok(Math.abs(cost(u)-.0008444)<1e-10);
 assert.throws(()=>cost({...u,output_tokens:101}),/Unaccounted/);
 assert.throws(()=>cost(null),/Missing/);
 assert.throws(()=>cost({...u,input_tokens:-1,input_token_details:{text_tokens:-1,audio_tokens:0}}),/Invalid/);
});
test('budget reserves unknown charges and rejects duplicate or excessive spending',()=>{
 const l={entries:[{id:'uncertain',reserved_usd:1.49}]};
 assert.throws(()=>reserve(l,{id:'next'},.51),/Budget/);
 assert.throws(()=>reserve({entries:[{id:'same',actual_usd:.01}]},{id:'same'}),/reconciliation/);
 const good={entries:[]};reserve(good,{id:'one'});
 assert.equal(good.entries[0].reserved_usd,RESERVATION);
 assert.throws(()=>reserve({entries:[{id:'broken',actual_usd:NaN}]},{id:'two'}),/Invalid budget/);
});
test('voice identities are disjoint and every cohort has both labels',()=>{
 const rows=plan();assert.equal(rows.length,1000);
 const owners=new Map(),groups=new Map();
 for(const r of rows){
  assert.ok(!r.real_child&&!r.family_inputs_used&&!r.reference_audio_used);
  assert.ok(!owners.has(r.speaker)||owners.get(r.speaker)===r.split);
  owners.set(r.speaker,r.split);
  const k=[r.split,r.accent,r.synthetic_style].join(':');
  if(!groups.has(k))groups.set(k,new Set());groups.get(k).add(r.label);
 }
 for(const labels of groups.values())assert.equal(labels.size,2);
 assert.equal(rows.filter(x=>x.split==='train').length,700);
 assert.equal(rows.filter(x=>x.split==='validation').length,150);
 assert.equal(rows.filter(x=>x.split==='test').length,150);
});
test('dual target changes derived labels without changing raw plans or partial negatives',()=>{
 const raw=plan(), before=JSON.stringify(raw);
 const revised=targetPlan(raw,{target:'hi-piku-piko-v2',accepted_names:['piku','piko'],declared_before_corpus_training:true});
 assert.equal(JSON.stringify(raw),before);
 for(const row of revised){
  if(row.text==='Hi, Piko!'){assert.equal(row.label,1);assert.equal(row.original_label,0);}
  if(['Hi!','Pikoo!','Hi, pee!','Hi, Tikoo!'].includes(row.text))assert.equal(row.label,0);
 }
 assert.throws(()=>targetPlan(raw,{target:'hi-piku-piko-v2',accepted_names:['piku'],declared_before_corpus_training:true}),/contract/);
});
test('bounded expansion supplies complete targets and rejected name-only prefixes using TRAIN voices',()=>{
 const rows=expansionPlan({target:'hi-piku-piko-v2'});
 assert.equal(rows.length,100);
 assert.equal(new Set(rows.map(r=>r.id)).size,100);
 for(const r of rows){
  assert.equal(r.split,'train');assert.ok(['marin','cedar','coral','alloy'].includes(r.voice));
  assert.equal(r.synthetic_style,'adult');assert.ok(!r.family_inputs_used&&!r.reference_audio_used);
  if(['Pikoo!','Piko!','Hi!','Hi, Tikoo!','Hi, Tiko!','Hi, pee!'].includes(r.text))assert.equal(r.label,0);
 }
 assert.equal(rows.filter(r=>r.label===1).length,40);
});
test('TEST remains closed without a DEV-qualified matching frozen model and target',()=>{
 const binary=Buffer.from('fixture'),crypto=require('crypto');
 const c={target:'hi-piku-piko-v2',accepted_names:['piku','piko']};
 const f={...c,candidate_frozen_at:'fixture',development_passed:true,model_sha256:crypto.createHash('sha256').update(binary).digest('hex')};
 validateFrozen(c,f,binary);
 assert.throws(()=>validateFrozen(c,{...f,development_passed:false},binary),/Qualified/);
 assert.throws(()=>validateFrozen(c,{...f,accepted_names:['piku']},binary),/names/);
 assert.throws(()=>validateFrozen(c,f,Buffer.from('changed')),/hash/);
});
