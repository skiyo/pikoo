import test from 'node:test';import assert from 'node:assert/strict';
import {memoryDeadline} from './memory-timeout.mjs';
import {createOpenAiCompatibleTextCall} from './node_modules/qwen-audio-agent/server/src/core/llm/openai-compatible-chat.mjs';
test('memory deadline is bounded and defaults to 45 seconds',()=>{assert.equal(memoryDeadline(),45000);assert.equal(memoryDeadline('30000'),30000);for(const x of ['NaN','0','60001','1.5'])assert.throws(()=>memoryDeadline(x));});
test('slow memory generation can finish while timeout still cancels a stalled request',async()=>{
 const fetchImpl=(_,o)=>new Promise((resolve,reject)=>{const timer=setTimeout(()=>resolve({ok:true,json:async()=>({choices:[{message:{content:'{"action":"none"}'}}]})}),30);o.signal.addEventListener('abort',()=>{clearTimeout(timer);reject(o.signal.reason);},{once:true});});
 const args={apiKey:'fixture-not-a-key',baseUrl:'https://example.invalid',model:'fixture',fetchImpl};
 await assert.rejects(createOpenAiCompatibleTextCall({...args,timeoutMs:5})({system:'',user:''}));
 assert.equal(await createOpenAiCompatibleTextCall({...args,timeoutMs:100})({system:'',user:''}),'{"action":"none"}');
});
