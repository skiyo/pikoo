import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {TerraClient} from './openai-terra.mjs';
import {CLASSIFIER_INSTRUCTIONS,INTERACTION_SCHEMA} from './live-idle.mjs';
import {UsageLedger} from './live-usage.mjs';
if(!process.env.PIKOO_EVAL_REPORT)throw new Error('Set PIKOO_EVAL_REPORT; this script makes 60 paid Responses calls');
const cases=JSON.parse(fs.readFileSync(new URL('./live-classification-cases.json',import.meta.url)));
const ledger=new UsageLedger({filePath:process.env.PIKOO_EVAL_REPORT+'.usage.json'}),client=new TerraClient({ledger});
const report={startedAt:new Date().toISOString(),syntheticScenarios:true,notFamilyAcceptance:true,promptSha256:createHash('sha256').update(CLASSIFIER_INSTRUCTIONS).digest('hex'),results:[]};
for(const [index,c] of cases.entries()) {
 const start=Date.now();let actual,error;
 try{actual=JSON.parse((await client.request({system:CLASSIFIER_INSTRUCTIONS,user:JSON.stringify({conversation:c.assistant?[{role:'assistant',content:c.assistant}]:[],segments:[{text:c.text}]}),schema:INTERACTION_SCHEMA,purpose:'classification-evaluation',timeoutMs:5000,maxOutputTokens:256})).text);}catch(e){error=e.code||e.name;actual={label:'unknown',farewell:false};}
 report.results.push({case:index+1,expected:c.label,expectedFarewell:c.farewell===true,actual,error,durationMs:Date.now()-start});
 fs.writeFileSync(process.env.PIKOO_EVAL_REPORT,JSON.stringify(report,null,2),{mode:0o600});
 if((index+1)%10===0)console.log(JSON.stringify({completed:index+1,total:cases.length}));
 await new Promise(resolve=>setTimeout(resolve,250));
}
report.byClass=Object.fromEntries(['directed','background','unknown'].map(label=>{const rows=report.results.filter(r=>r.expected===label);return [label,{total:rows.length,correct:rows.filter(r=>!r.error&&r.actual.label===label).length}];}));
report.farewellCorrect=report.results.filter(r=>!r.error&&r.actual.farewell===r.expectedFarewell).length;
report.errors=report.results.filter(r=>r.error).length;report.usage=ledger.report();report.finishedAt=new Date().toISOString();
fs.writeFileSync(process.env.PIKOO_EVAL_REPORT,JSON.stringify(report,null,2),{mode:0o600});console.log(JSON.stringify({byClass:report.byClass,farewellCorrect:report.farewellCorrect,errors:report.errors,usage:report.usage},null,2));
