// SPDX-License-Identifier: Apache-2.0
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('fs'),os=require('os'),path=require('path'),{spawnSync}=require('child_process');
const {sourcePreflight}=require('./wake_mixed_test_generate.cjs');
test('mixed source CLI rejects missing and excessive scope before reading keys or writing output',()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'pikoo-mixed-preflight-'));
 try{
  const a=Object.fromEntries(['python','protocol','policy','model','protected-hashes','native-proof','isolation','output','budget-root','key-file'].map(k=>[k,path.join(root,k)]));
  assert.throws(()=>sourcePreflight({...a,'new-attempt-limit':'71'}),/At most70/);
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
