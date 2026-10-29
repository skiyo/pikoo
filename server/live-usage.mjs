import fs from 'node:fs';
import path from 'node:path';

// USD, Standard rates verified 2026-10-29. This is a Pikoo ledger, not an account balance.
export const PRICES={liveSecond:0.05/60,input:1/1e6,cached:0.05/1e6,output:5/1e6,cacheWrite30m:1.25/1e6};
export class UsageLedger {
  constructor({filePath,periodStart=null,periodEnd=null,now=Date.now}={}) {
    this.path=filePath;this.now=now;this.records={};this.warnings=[];
    this.period={start:periodStart,end:periodEnd,verified:Boolean(periodStart&&periodEnd)};
    if(filePath&&fs.existsSync(filePath)) {const data=JSON.parse(fs.readFileSync(filePath,'utf8'));this.records=data.records||{};this.warnings=data.warnings||[];}
  }
  save() {
    // User opted out of credit-cycle warnings; retain usage without imposing a budget stop.
    if(!this.path)return;
    fs.mkdirSync(path.dirname(this.path),{recursive:true,mode:0o700});
    fs.writeFileSync(this.path+'.tmp',JSON.stringify({records:this.records,warnings:this.warnings}),{mode:0o600});
    fs.renameSync(this.path+'.tmp',this.path);
  }
  live(id,seconds,{final=false,estimated=false}={}) {
    if(!id||!Number.isFinite(seconds)||seconds<0)return;
    const prior=this.records[`live:${id}`];
    if(prior?.final)return;
    const duration=final?seconds:Math.max(seconds,prior?.seconds||0);
    this.records[`live:${id}`]={kind:'live',at:prior?.at||this.now(),seconds:duration,usd:duration*PRICES.liveSecond,final,estimated};this.save();
  }
  response(id,purpose,usage,model) {
    if(!id||!usage||this.records[`response:${id}`])return;
    const input=Number(usage.input_tokens)||0,output=Number(usage.output_tokens)||0;
    const cached=Math.min(input,Number(usage.input_tokens_details?.cached_tokens)||0);
    const write=Math.min(input-cached,Number(usage.input_tokens_details?.cache_write_tokens)||0);
    // Reasoning tokens are already included in output_tokens.
    this.records[`response:${id}`]={kind:'terra',purpose,model,at:this.now(),usage,
      usd:(input-cached-write)*PRICES.input+cached*PRICES.cached+write*PRICES.cacheWrite30m+output*PRICES.output};this.save();
  }
  report() {
    const rows=Object.values(this.records).filter(r=>!this.period.verified||(r.at>=Date.parse(this.period.start)&&r.at<Date.parse(this.period.end)));
    return {period:this.period,scope:this.period.verified?'configured-credit-period':'all-recorded-usage-period-unverified',
      usd:rows.reduce((a,r)=>a+r.usd,0),liveSeconds:rows.filter(r=>r.kind==='live').reduce((a,r)=>a+r.seconds,0),
      unfinalized:rows.filter(r=>r.kind==='live'&&!r.final).length,byPurpose:Object.fromEntries([...new Set(rows.map(r=>r.purpose||r.kind))].map(p=>[p,rows.filter(r=>(r.purpose||r.kind)===p).reduce((a,r)=>a+r.usd,0)])),warnings:this.warnings};
  }
}
