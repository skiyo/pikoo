// SPDX-License-Identifier: Apache-2.0
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {cost,reserve,plan,targetPlan,expansionPlan,adultRefreshPlan,validateFrozen,generationCount,freshTestPlan,RESERVATION}=require('./hi_pikoo_generate.cjs');
test('adult coverage refresh stays TRAIN-only, held-out voices untouched and has a bounded diverse pilot',()=>{
 const rows=adultRefreshPlan({target:'hi-piku-piko-v2'}),pilot=rows.slice(0,20);
 assert.equal(rows.length,200);assert.equal(rows.filter(r=>r.label).length,160);
 assert.equal(new Set(rows.map(r=>r.id)).size,200);
 assert.ok(rows.every(r=>r.split==='train'&&r.synthetic_style==='adult'&&r.synthetic&&!r.real_child&&!r.family_inputs_used&&!r.reference_audio_used));
 assert.deepEqual([...new Set(pilot.map(r=>r.voice))].sort(),['alloy','cedar','coral','marin']);
 assert.deepEqual([...new Set(pilot.map(r=>r.accent))].sort(),['Chinese-accent','standard']);
 assert.ok(rows.every(r=>!['echo','shimmer','ash','sage','ballad','verse'].includes(r.voice)));
 assert.ok(rows.some(r=>!r.label&&r.text==='Hi, Tikoo!'));
 assert.throws(()=>adultRefreshPlan({target:'other'}),/dual target/);
});
test('ASR shares the dollar budget but not the synthesis request count',()=>{
 const entries=Array.from({length:509},(_,i)=>({id:'legacy-'+i,reserved_usd:.001}));
 entries.push(...Array.from({length:553},(_,i)=>({id:'blind-ASR-'+i,model:'gpt-transcribe',actual_usd:.0001})));
 assert.equal(generationCount({entries}),509);
 entries.push({id:'unknown',model:'unknown-provider',reserved_usd:.012});
 assert.equal(generationCount({entries}),510);
});
test('fresh TEST uses reserved untouched identities and unique ids, not old ballad or verse',()=>{
 const used=['openai:cedar','openai:ash','openai:sage','openai:ballad','openai:verse'];
 const isolation={target:'hi-piku-piko-v2',reserved_source_speakers:['openai:echo','openai:shimmer'],
  used_source_speakers:used,covered_splits:['test','train','validation'],metadata_only:true,audio_read:false,household_used:false};
 const frozen={target:isolation.target,required_fresh_test_speakers:isolation.reserved_source_speakers,forbidden_test_speakers:used};
 const rows=plan(),mapped=freshTestPlan(rows,isolation,frozen);
 assert.deepEqual(mapped.filter(r=>r.split!=='test'),rows.filter(r=>r.split!=='test'));
 assert.deepEqual([...new Set(mapped.filter(r=>r.split==='test').map(r=>r.speaker))],isolation.reserved_source_speakers);
 assert.ok(mapped.filter(r=>r.split==='test').every(r=>r.id.startsWith('native-fresh2-')&&!used.includes(r.speaker)));
 assert.throws(()=>freshTestPlan(rows,{...isolation,used_source_speakers:[...used,'openai:echo']},frozen),/isolation mismatch/);
 assert.throws(()=>freshTestPlan(rows,{...isolation,covered_splits:['train']},frozen),/isolation mismatch/);
});
test('reasoning is not charged twice and unaccounted usage fails closed',()=>{
 const u={input_tokens:98,output_tokens:100,input_token_details:{text_tokens:98,audio_tokens:0},output_token_details:{text_tokens:69,audio_tokens:31,reasoning_tokens:54}};
 assert.ok(Math.abs(cost(u)-.0008444)<1e-10);
 assert.throws(()=>cost({...u,output_tokens:101}),/Unaccounted/);
 assert.throws(()=>cost(null),/Missing/);
 assert.throws(()=>cost({...u,input_tokens:-1,input_token_details:{text_tokens:-1,audio_tokens:0}}),/Invalid/);
 const heard={...u,input_tokens:110,input_token_details:{text_tokens:98,audio_tokens:12}};
 assert.ok(Math.abs(cost(heard)-.0009644)<1e-10);
 assert.throws(()=>cost({...heard,input_tokens:111}),/Unaccounted/);
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
 const trial={...f,development_passed:false,trial_authorized:true,status:'best-available-unqualified-trial',formal_goal_passed:false,release_eligible:false};
 assert.throws(()=>validateFrozen(c,trial,binary),/Qualified/);
 validateFrozen(c,trial,binary,true);
 assert.throws(()=>validateFrozen(c,{...trial,formal_goal_passed:true},binary,true),/Qualified/);
});
