import path from 'node:path';
import { createOpenAiCompatibleTextCall } from './node_modules/qwen-audio-agent/server/src/core/llm/openai-compatible-chat.mjs';
import { createMemoryModule } from './node_modules/qwen-audio-agent/server/src/memory/module.mjs';
import { optionalModuleFactories } from './node_modules/qwen-audio-agent/server/src/app/optional-modules.mjs';
import { ContextLearningQueue, familyLearningPolicy } from './context-learning.mjs';
import { memoryDeadline } from './memory-timeout.mjs';

// Fixed-version composition adapter; no installed package files are changed.
export function installContextLearning() {
  const index = optionalModuleFactories.indexOf(createMemoryModule);
  if (index < 0) throw new Error('Pinned memory composition changed; review context adapter');
  let queue, textCall;
  optionalModuleFactories[index] = args => {
    textCall = args.config.memoryAutoEnabled ? createOpenAiCompatibleTextCall({
      baseUrl: args.config.memoryBaseUrl, apiKey: args.config.memoryApiKey,
      model: args.config.memoryModel, timeoutMs: memoryDeadline(),
    }) : null;
    const module = createMemoryModule({ ...args,
      // Shared-family speech does not establish an individual speaker profile.
      config: { ...args.config, preferenceLearningEnabled: false },
      textModelCall: textCall ? request => textCall({ ...request,
        system: request.system + '\n\n' + familyLearningPolicy }) : null,
    });
    if (!textCall) return module;
    const memory = module.services.frontendMemory;
    const observer = module.sessionObservers.find(o => o.memoryExtractor);
    if (!memory || !observer?.memoryExtractor?.run) throw new Error('Pinned learning observer changed');
    queue = new ContextLearningQueue({
      filePath: path.join(path.dirname(args.config.memoryAuditPath), 'pikoo-context-learning.json'),
      memory, conversationSync: args.conversationSync, extractor: observer.memoryExtractor,
      audit: args.audit, logger: args.logger,
    });
    observer.memoryExtractor = { maybeRun: args => queue.enqueue('memory', args) };
    const originalApply = memory.apply.bind(memory);
    memory.apply = async (ownerId, changes, context, isCurrent) => {
      const result = await originalApply(ownerId, changes, context, isCurrent);
      if (result?.changed && ['gateway-memory-api','realtime-tool'].includes(context?.source)
          && changes.some(c => c.edits?.some(e => e.old_text && e.old_text !== e.new_text)))
        queue.clearSummaries(ownerId);
      return result;
    };
    const originalClose = module.close;
    module.close = async () => { await queue.close(); return originalClose(); };
    const originalMount = module.mountRoutes;
    module.mountRoutes = app => {
      originalMount(app);
      app.get('/api/pikoo/context-status', (req,res) => res.json({
        timeZone:'Asia/Shanghai', automaticMemory:true, learning:queue.health(req.identity.ownerId),
        digestCount:queue.summariser?.digestPool?.count(req.identity.ownerId) || 0,
      }));
    };
    module.services.contextLearningQueue = queue;
    return module;
  };
  return {
    bind(app) {
      if (!queue) return;
      if (app.services.sessionSummariser) app.services.sessionSummariser.llmCall = textCall;
      queue.bindSummariser(app.services.sessionSummariser); queue.start();
    },
  };
}
