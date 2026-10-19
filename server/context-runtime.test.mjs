import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { once } from 'node:events';
import { installContextLearning } from './context-runtime.mjs';
import { optionalModuleFactories } from './node_modules/qwen-audio-agent/server/src/app/optional-modules.mjs';
import { createMemoryModule } from './node_modules/qwen-audio-agent/server/src/memory/module.mjs';
import { ConversationSync } from './node_modules/qwen-audio-agent/server/src/conversation/conversation-sync.mjs';
import { SessionSummariser } from './node_modules/qwen-audio-agent/server/src/conversation/session-summariser.mjs';
import { SessionDigestPool } from './node_modules/qwen-audio-agent/server/src/conversation/session-digest.mjs';

test('pinned composition automatically learns one unprompted fact, summarises, and deletes safely',async t=>{
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'pikoo-composition-'));let requests=0;
  t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  const api=http.createServer(async(req,res)=>{
    let body='';for await(const chunk of req)body+=chunk;
    const data=JSON.parse(body);requests++;
    const summary=data.messages[0].content.includes('这场对话聊了什么');
    if(!summary)assert.match(data.messages[0].content,/家庭共用宠物/);
    res.setHeader('content-type','application/json');res.end(JSON.stringify({choices:[{message:{content:JSON.stringify(summary
      ? {topics:['家庭天文'],gist:'讨论每周日全家一起观察星空。'}
      : {changes:[{document:'memory',edits:[],append:'- 家庭每周日一起观察星空。'}]})}}]}));
  });
  api.listen(0,'127.0.0.1');await once(api,'listening');t.after(()=>new Promise(r=>api.close(r)));
  const index=optionalModuleFactories.indexOf(createMemoryModule);installContextLearning();
  t.after(()=>{optionalModuleFactories[index]=createMemoryModule;});
  const sync=new ConversationSync(),logger={warn(){},debug(){}};
  const config={memoryAutoEnabled:true,memoryBaseUrl:`http://127.0.0.1:${api.address().port}/v1`,memoryApiKey:'local-test-key',memoryModel:'local-stub',
    memoryAuditPath:path.join(dir,'audit.jsonl'),userModelPath:path.join(dir,'USER.md'),frontendMemoryPath:path.join(dir,'MEMORY.md'),personalOwnerId:'owner',memoryProvider:'markdown'};
  const module=optionalModuleFactories[index]({config,logger,conversationSync:sync});t.after(()=>module.close());
  const q=module.services.contextLearningQueue;q.minGapMs=0;
  const pool=new SessionDigestPool();
  q.bindSummariser(new SessionSummariser({digestPool:pool,conversationSync:sync,logger,
    llmCall:async request=>{
      const r=await fetch(config.memoryBaseUrl+'/chat/completions',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({messages:[{role:'system',content:request.system},{role:'user',content:request.user}]})});
      return (await r.json()).choices[0].message.content;
    }}));
  sync.record({ownerId:'owner',sessionId:'one',id:'fact',role:'user',source:'voice-user',content:'我们全家每周日一起观察星空。'});
  await module.sessionObservers[0].onSessionClosed({ownerId:'owner',sessionId:'one',logger});
  q.summariser.maybeRun({ownerId:'owner',sessionId:'one'});
  assert.equal(q.health().pending,2);await q.runOne();await q.runOne();
  const memory=module.services.frontendMemory;const doc=memory.list('owner').find(x=>x.scope==='memory');
  assert.match(doc.content,/每周日一起观察星空/);assert.equal(requests,2);assert.equal(pool.count('owner'),1);
  await memory.apply('owner',[{document:'memory',expectedRevision:doc.revision,edits:[{old_text:'- 家庭每周日一起观察星空。',new_text:''}]}],{source:'realtime-tool'});
  assert.equal(pool.count('owner'),0);assert.equal(q.health().pending,0);
  assert(!memory.list('owner').find(x=>x.scope==='memory').content.includes('每周日一起观察星空'));
  assert.equal(module.services.profileObserver,null);
});
