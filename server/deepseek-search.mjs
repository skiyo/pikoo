// Raw Search API adapter; this does not call a DeepSeek language model.
// https://api-docs.deepseek.com/zh-cn/guides/search/
export class SearchError extends Error {
  constructor(code) { super(code); this.name='SearchError'; this.code=code; }
}
const endpoint='https://api.deepseek.com/v1/tools/search';
const maxResponseBytes=256*1024;
const text=(v,n)=>typeof v==='string'?[...v].slice(0,n).join(''):'';
async function readJson(response) {
  const reader=response.body?.getReader();
  if(!reader)throw new SearchError('deepseek_invalid_response');
  const chunks=[];let bytes=0;
  try {
    for(;;){const {value,done}=await reader.read();if(done)break;
      bytes+=value.byteLength;
      if(bytes>maxResponseBytes)throw new SearchError('deepseek_response_too_large');
      chunks.push(value);
    }
  } catch(e) {await reader.cancel().catch(()=>{});throw e;}
  try{return JSON.parse(Buffer.concat(chunks).toString('utf8'));}
  catch{throw new SearchError('deepseek_invalid_response');}
}
export class DeepSeekSearchProvider {
  constructor({apiKey=process.env.DEEPSEEK_API_KEY,fetchImpl=globalThis.fetch,timeoutMs=8000}={}) {
    this.apiKey=String(apiKey||'').trim();this.fetchImpl=fetchImpl;this.timeoutMs=timeoutMs;
  }
  describe(){return {key:'deepseek',label:'DeepSeek Search'};}
  isConfigured(){return Boolean(this.apiKey);}
  async search(query,{limit=5,signal}={}) {
    if(!this.isConfigured())throw new SearchError('deepseek_not_configured');
    if(typeof query!=='string'||![...query.trim()].length||[...query.trim()].length>128)
      throw new SearchError('deepseek_invalid_query');
    const count=Number.isFinite(Number(limit))?Math.max(1,Math.min(8,Math.trunc(Number(limit)))):5;
    const deadline=AbortSignal.timeout(this.timeoutMs);
    const callSignal=signal?AbortSignal.any([signal,deadline]):deadline;
    try {
      const response=await this.fetchImpl(endpoint,{method:'POST',redirect:'error',
        headers:{Authorization:`Bearer ${this.apiKey}`,'Content-Type':'application/json'},
        body:JSON.stringify({query:query.trim(),count,need_content:false}),signal:callSignal});
      if(!response.ok){
        await response.body?.cancel().catch(()=>{});
        const codes={400:'invalid_query',401:'authentication',402:'insufficient_balance',403:'permission',429:'rate_limited'};
        throw new SearchError('deepseek_'+(codes[response.status]||(response.status>=500?'unavailable':'request_rejected')));
      }
      const data=await readJson(response);
      if(!Array.isArray(data?.results))throw new SearchError('deepseek_invalid_response');
      return {results:data.results.slice(0,count).map(r=>({
        title:text(r?.title,300),url:text(r?.url,8192),
        snippet:text(r?.summary||r?.snippet,1200),source:text(r?.site_name,120),
        ...(typeof r?.date==='string'&&Number.isFinite(Date.parse(r.date))?{publishedAt:r.date}:{}),
      }))};
    } catch(e) {
      if(deadline.aborted)throw new SearchError('deepseek_timeout');
      if(signal?.aborted)throw new SearchError('deepseek_cancelled');
      if(e instanceof SearchError)throw e;
      // Do not echo remote response bodies, request headers or transport errors.
      throw new SearchError('deepseek_network');
    }
  }
}
