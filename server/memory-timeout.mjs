import { createOpenAiCompatibleTextCall } from './node_modules/qwen-audio-agent/server/src/core/llm/openai-compatible-chat.mjs';
import { createMemoryModule } from './node_modules/qwen-audio-agent/server/src/memory/module.mjs';
import { optionalModuleFactories } from './node_modules/qwen-audio-agent/server/src/app/optional-modules.mjs';
export function memoryDeadline(value=process.env.PIKOO_MEMORY_TIMEOUT_MS){
  const ms=value===undefined?45000:Number(value);
  if(!Number.isInteger(ms)||ms<1000||ms>60000)throw new Error('PIKOO_MEMORY_TIMEOUT_MS must be 1000..60000');
  return ms;
}
// qwen-audio-agent@2.0.1 has a fixed 10s background text deadline and no config
// knob. Its exported composition array lets us replace only the memory module's
// text caller, without modifying package files or weakening learning boundaries.
export function installMemoryDeadline(){
  const index=optionalModuleFactories.indexOf(createMemoryModule);
  if(index<0)throw new Error('Memory composition changed; review pinned adapter');
  const timeoutMs=memoryDeadline();
  optionalModuleFactories[index]=args=>createMemoryModule({...args,textModelCall:args.config.memoryAutoEnabled?createOpenAiCompatibleTextCall({baseUrl:args.config.memoryBaseUrl,apiKey:args.config.memoryApiKey,model:args.config.memoryModel,timeoutMs}):null});
}
