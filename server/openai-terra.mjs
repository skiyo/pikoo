import { randomUUID } from 'node:crypto';

export const TERRA_MODEL = 'gpt-6.1-terra';
export class TerraClient {
  constructor({apiKey=process.env.OPENAI_API_KEY, fetchImpl=fetch, ledger=null}={}) {
    this.apiKey=apiKey; this.fetch=fetchImpl; this.ledger=ledger;
  }
  async request({system, user, schema, purpose='task', timeoutMs=20000, maxOutputTokens=2048, signal}={}) {
    if(!this.apiKey) throw Object.assign(new Error('OpenAI key is not configured'),{code:'missing_key'});
    const id=randomUUID();
    const response=await this.fetch('https://api.openai.com/v1/responses', {
      method:'POST', headers:{Authorization:`Bearer ${this.apiKey}`,'Content-Type':'application/json'},
      signal: signal ? AbortSignal.any([signal,AbortSignal.timeout(timeoutMs)]) : AbortSignal.timeout(timeoutMs),
      body:JSON.stringify({model:TERRA_MODEL,store:false,service_tier:'default',reasoning:{effort:'low'},
        instructions:system,input:user,max_output_tokens:maxOutputTokens,
        ...(schema?{text:{format:{type:'json_schema',name:'interaction',strict:true,schema}}}:{})}),
    });
    const data=await response.json();
    if(!response.ok) throw Object.assign(new Error(`Terra request failed (${response.status})`),{
      code:data.error?.code||`http_${response.status}`,status:response.status});
    this.ledger?.response(data.id||id,purpose,data.usage,data.model);
    if(data.status && data.status!=='completed') throw Object.assign(new Error('Terra response incomplete'),{code:data.incomplete_details?.reason||data.status});
    const text=(data.output||[]).flatMap(item=>item.content||[]).filter(p=>p.type==='output_text').map(p=>p.text).join('');
    if(!text) throw Object.assign(new Error('Terra returned no text'),{code:'empty_response'});
    return {text,usage:data.usage,id:data.id,model:data.model};
  }
  textCall(purpose='memory',timeoutMs=45000) { return async request=>(await this.request({timeoutMs,...request,purpose})).text; }
}
