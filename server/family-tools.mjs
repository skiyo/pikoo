import {DeepSeekSearchProvider} from './deepseek-search.mjs';
import {SafeUrlFetcher} from './node_modules/qwen-audio-agent/server/src/frontend/retrieval/safe-url-fetcher.mjs';

export function familyToolsOptions(env=process.env) {
  const reader=new SafeUrlFetcher({timeoutMs:8000,maxBytes:1024*1024,maxChars:12000,maxRedirects:3});
  return {
    webSearchProvider:new DeepSeekSearchProvider({apiKey:env.DEEPSEEK_API_KEY}),
    urlFetcher:{async fetch(url,{signal}={}){
      const deadline=AbortSignal.timeout(8000);
      const combined=signal?AbortSignal.any([signal,deadline]):deadline;
      return reader.fetch(url,{signal:combined});
    }},
  };
}
