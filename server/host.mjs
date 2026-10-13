import { installMemoryDeadline } from './memory-timeout.mjs';
import { once } from 'node:events';
import { acquireGatewayLease } from 'qwen-audio-agent/gateway-lease';
import { createGatewayApplication } from 'qwen-audio-agent/gateway-application';
import { createRealtimeProviderRegistry } from 'qwen-audio-agent/realtime-provider';
import { pikooGoogleLiveProvider } from './google-live-compat.mjs';
installMemoryDeadline();
const lease=acquireGatewayLease('/var/lib/pikoo/qwaudio/state',{owner:'pikoo-systemd'});
process.env.QWEN_AUDIO_GATEWAY_INSTANCE_ID=lease.instanceId;
process.env.QWEN_AUDIO_GATEWAY_STARTED_AT=new Date().toISOString();
const app=createGatewayApplication({realtimeProviderRegistry:createRealtimeProviderRegistry({providers:[pikooGoogleLiveProvider],defaultProvider:'google-live'}),realtimeProvider:'google-live'});
if(!app.server.listening)await once(app.server,'listening');
lease.update({state:'ready',origin:'http://127.0.0.1:3101'});
const heartbeat=setInterval(()=>lease.update(),15000);heartbeat.unref();
let closing;
function stop(){
 if(closing)return closing;
 clearInterval(heartbeat);
 const timeout=setTimeout(()=>process.exit(1),80000);timeout.unref();
 closing=app.close().then(()=>{lease.release();process.exit(0)}).catch(e=>{console.error(e.message);lease.release();process.exit(1)});
 return closing;
}
process.once('SIGTERM',stop);process.once('SIGINT',stop);process.once('exit',()=>lease.release());
