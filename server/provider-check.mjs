import WebSocket from './node_modules/ws/wrapper.mjs';
process.loadEnvFile('/var/lib/pikoo/qwaudio/config.env');
const key=process.env.GOOGLE_API_KEY;
const clean=s=>String(s).replaceAll(key,'[REDACTED]');
const classify=s=> /location|region|country/i.test(s)?'region_restricted':/resource.exhausted|quota|rate.limit|429/i.test(s)?'quota_exhausted':/api.key|unauthenticated|permission.denied|401|403/i.test(s)?'key_or_permission':/timeout|timed out|ECONN|ENET|ENOTFOUND/i.test(s)?'network':'provider_error';
console.log(JSON.stringify({at:new Date().toISOString(),uid:process.getuid(),liveModel:process.env.GOOGLE_LIVE_REALTIME_MODEL,memoryModel:process.env.QWEN_AUDIO_MEMORY_MODEL}));
let failures=0;
try{
 const r=await fetch('https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',{method:'POST',headers:{Authorization:'Bearer '+key,'Content-Type':'application/json'},body:JSON.stringify({model:process.env.QWEN_AUDIO_MEMORY_MODEL,messages:[{role:'user',content:'只回复：连接正常。'}],max_tokens:256}),signal:AbortSignal.timeout(25000)});
 const data=await r.json();
 if(!r.ok)throw Error(JSON.stringify({status:r.status,error:data.error}));
 if(!data.choices?.[0]?.message?.content)throw Error('Provider returned no text');
 console.log(JSON.stringify({check:'memory_text',ok:true,status:r.status,model:data.model,text:data.choices?.[0]?.message?.content}));
}catch(e){failures++;console.log(JSON.stringify({check:'memory_text',ok:false,category:classify(String(e)),error:clean(e)}));}
await new Promise(resolve=>{
 const url=new URL('wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent');url.searchParams.set('key',key);
 const ws=new WebSocket(url,{handshakeTimeout:20000});let finished=false;
 const done=(ok,reason)=>{if(finished)return;finished=true;clearTimeout(timer);if(!ok)failures++;console.log(JSON.stringify({check:'live_setup',ok,...(!ok?{category:classify(reason),error:clean(reason)}:{})}));ws.close();resolve()};
 const timer=setTimeout(()=>done(false,'Live setup timeout'),25000);
 ws.on('open',()=>ws.send(JSON.stringify({setup:{model:'models/'+process.env.GOOGLE_LIVE_REALTIME_MODEL,generationConfig:{responseModalities:['AUDIO']}}})));
 ws.on('message',raw=>{const e=JSON.parse(raw);if(e.setupComplete)done(true);if(e.error)done(false,JSON.stringify(e.error))});
 ws.on('error',e=>done(false,e.message));ws.on('close',(code,reason)=>{if(!finished)done(false,`close ${code}: ${reason}`)});
});
process.exitCode=failures?1:0;
