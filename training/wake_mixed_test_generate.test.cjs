// SPDX-License-Identifier: Apache-2.0
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('fs'),os=require('os'),path=require('path'),{spawnSync}=require('child_process');
const {sourcePreflight}=require('./wake_mixed_test_generate.cjs');
test('mixed source CLI rejects missing and excessive scope before reading keys or writing output',()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'pikoo-mixed-preflight-'));
 try{
  const a=Object.fromEntries(['python','protocol','policy','model','protected-hashes','native-proof','isolation','output','budget-root','key-file'].map(k=>[k,path.join(root,k)]));
  assert.throws(()=>sourcePreflight({...a,'new-attempt-limit':'71'}),/At most70/);
  assert.throws(()=>sourcePreflight({...a,'source-repair':path.join(root,'unapproved-plan'),'new-attempt-limit':'5'}),/At most4/);
  assert.throws(()=>sourcePreflight({...a,'source-repair':path.join(root,'unapproved-plan'),'new-attempt-limit':'1'}),/preflight failed before credentials/);
  assert.throws(()=>sourcePreflight({...a,'new-attempt-limit':'1'}),/preflight failed before credentials/);
  assert.ok(!fs.existsSync(a.output));assert.ok(!fs.existsSync(a['budget-root']));
 }finally{fs.rmSync(root,{recursive:true,force:true});}
});
test('mixed generation CLI cannot initialize a new budget/output on a failed protocol',()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'pikoo-mixed-cli-'));
 try{
  const names=['python','protocol','policy','model','protected-hashes','native-proof','isolation','output','budget-root','key-file'];
  const result=spawnSync(process.execPath,[path.join(__dirname,'wake_mixed_test_generate.cjs'),
   ...names.flatMap(k=>['--'+k,path.join(root,k)])],{encoding:'utf8',timeout:5000});
  assert.equal(result.status,1);assert.match(result.stderr,/preflight failed before credentials/);
  assert.ok(!fs.existsSync(path.join(root,'output')));assert.ok(!fs.existsSync(path.join(root,'budget-root')));
 }finally{fs.rmSync(root,{recursive:true,force:true});}
});
test('approved repair shape keeps full scope, four literal requests and a separate private output',()=>{
 const root=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'pikoo-repair-shape-')));
 try{
  const plan={scope:'synthetic-source-sub-bundle-not-full-TEST',full_TEST_complete:false,
   whole_TEST_slots:150,synthetic_slots:70,family_slots_still_required:80,
   source_repair_requests:4,original70_sources_retained:true,automatic_retry:false,
   source_repair_plan_sha256:'a'.repeat(64),shared_budget_root:root,
   rows:Array.from({length:4},()=>({source_repair_plan_sha256:'a'.repeat(64),generation_request_policy:'literal-target-response-v2'}))};
  const executable=path.join(root,'fixture-python'),payload=path.join(root,'fixture-plan.json');
  // Fixture-only transport for the already unit-tested Python proof gate.
  fs.writeFileSync(executable,'#!/bin/sh\nexec /bin/cat "$(dirname "$0")/fixture-plan.json"\n',{mode:0o700});
  fs.writeFileSync(payload,JSON.stringify(plan));
  const a=Object.fromEntries(['protocol','policy','model','protected-hashes','native-proof','isolation','key-file'].map(k=>[k,path.join(root,k)]));
  Object.assign(a,{python:executable,output:path.join(root,'source-repair1'),'source-repair':path.join(root,'source-repair1-plan.json'),'budget-root':root});
  assert.equal(sourcePreflight(a).limit,4);
  assert.throws(()=>sourcePreflight({...a,output:path.join(root,'synthetic')}),/private source subdirectory/);
  fs.writeFileSync(payload,JSON.stringify({...plan,rows:plan.rows.slice(1)}));
  assert.throws(()=>sourcePreflight(a),/Full mixed TEST scope/);
  fs.writeFileSync(payload,JSON.stringify({...plan,automatic_retry:true}));
  assert.throws(()=>sourcePreflight(a),/Source repair proof/);
  assert.ok(!fs.existsSync(a.output));assert.ok(!fs.existsSync(a['key-file']));
 }finally{fs.rmSync(root,{recursive:true,force:true});}
});
