// Explicit sample-based end-to-end test; no microphone permission is requested.
import fs from 'node:fs';
import {WebSocket} from '../server/node_modules/ws/wrapper.mjs';
import {DeviceSession} from '../firmware/simulator/session.mjs';
const file=process.argv[2];if(!file)throw Error('Usage: node tools/check-wake-to-session.mjs /private/16khz-mono-pcm16.wav');
const port=Number(process.env.PIKOO_SIM_PORT||8793),origin=`http://127.0.0.1:${port}`;
const mode=await(await fetch(`${origin}/mode`)).json();if(!mode.wake||mode.mode!=='live')throw Error('Requires local wake worker and explicit live simulator configuration');
const wav=fs.readFileSync(file);let pcm,format;
if(wav.toString('ascii',0,4)!=='RIFF'||wav.toString('ascii',8,12)!=='WAVE')throw Error('Requires WAV');
for(let offset=12;offset+8<=wav.length;){const size=wav.readUInt32LE(offset+4),name=wav.toString('ascii',offset,offset+4);if(offset+8+size>wav.length)throw Error('Truncated WAV');if(name==='fmt ')format=wav.subarray(offset+8,offset+8+size);if(name==='data')pcm=wav.subarray(offset+8,offset+8+size);offset+=8+size+size%2;}
if(!format||format.readUInt16LE(0)!==1||format.readUInt16LE(2)!==1||format.readUInt32LE(4)!==16000||format.readUInt16LE(14)!==16||!pcm)throw Error('Requires 16kHz mono PCM16 WAV');
const input=Buffer.concat([Buffer.alloc(32000),pcm,Buffer.alloc(32000)]),delay=ms=>new Promise(r=>setTimeout(r,ms));
let device,wakeDetected=false,connected=false,score=0;
const wake=new WebSocket(`${origin.replace('http:','ws:')}/wake`,{origin});
const session=new DeviceSession({send:e=>device?.readyState===1&&device.send(JSON.stringify(e)),stopAudio:()=>{},playAudio:async()=>{},stateChanged:()=>{}});
const began=Date.now();let done;
const completion=new Promise(resolve=>done=resolve),timer=setTimeout(()=>done(false),60000);
wake.on('message',async data=>{
 const e=JSON.parse(data);
 if(e.type==='ready'){
  if(e.modelSha256!==mode.wakeModel.sha256){done(false);return;}
  for(let i=0;i+640<=input.length;i+=640){if(wake.readyState!==1)break;wake.send(input.subarray(i,i+640));await delay(20);}
 }
 if(e.type==='wake'&&!wakeDetected){wakeDetected=true;score=e.score;wake.close();const hello=session.wake();device=new WebSocket(`${origin.replace('http:','ws:')}/device`,{origin});device.on('open',()=>device.send(JSON.stringify(hello)));device.on('message',d=>{const m=JSON.parse(d);session.receive(m);if(m.type==='voice.ready'){connected=true;done(true);}});device.on('error',()=>done(false));}
});
wake.on('error',()=>done(false));
const ok=await completion;clearTimeout(timer);session.stop();wake.close();device?.close();
const result={ok,modelBytes:mode.wakeModel.bytes,wakeDetected,score,voiceReady:connected,durationSeconds:(Date.now()-began)/1000,scope:'Private synthesized WAV -> local V5 -> GCP ready; not human microphone validation'};
fs.writeFileSync(new URL('../firmware/build-host/wake-to-session.json',import.meta.url),JSON.stringify(result,null,2));console.log(JSON.stringify(result));if(!ok)process.exitCode=1;
