import test from 'node:test';
import assert from 'node:assert/strict';
import {PcmOutputGain,liveOutputGainDb,pcmRms} from './live-audio.mjs';
import {liveConfig,liveVoice,LIVE_VOICES} from './openai-live.mjs';

for(const db of [4,6,12])test(`quiet PCM receives +${db}dB without duration, sample rate or packet-boundary changes`,()=>{
 const pcm=Buffer.alloc(32000);for(let i=0;i<16000;i++)pcm.writeInt16LE(Math.round(3000*Math.sin(i*.13)),i*2);
 const gain=new PcmOutputGain(db),out=gain.append(pcm),split=new PcmOutputGain(db),parts=[];
 for(let pos=0;pos<pcm.length;pos+=254)parts.push(split.append(pcm.subarray(pos,pos+254)));
 assert.deepEqual(Buffer.concat(parts),out);assert.equal(out.length,pcm.length);
 assert(Math.abs(20*Math.log10(pcmRms(out)/pcmRms(pcm))-db)<.002);
 assert.equal(gain.limitedSamples,0);assert(Math.abs(gain.stats().measuredGainDb-db)<.002);assert(gain.stats().maxDeliveredRms>gain.stats().maxSourceRms);assert.deepEqual(new PcmOutputGain(0).append(pcm),pcm);
});

test('output soft knee bounds full-scale peaks symmetrically without wrap or hard clipping',()=>{
 const input=Buffer.alloc(65536*2);for(let i=-32768;i<=32767;i++)input.writeInt16LE(i,(i+32768)*2);
 const gain=new PcmOutputGain(12),out=gain.append(input);let prior=-32768;
 for(let i=0;i<out.length;i+=2){const value=out.readInt16LE(i);assert(Math.abs(value)<=Math.ceil(.94*32768));assert(value>=prior);prior=value;}
 assert(gain.limitedSamples>0);
 assert.throws(()=>gain.append(Buffer.alloc(1)),/even/);
});

test('output settings reject invalid gains and untested voices before making requests',()=>{
 for(const value of [-1,13,NaN,Infinity,'invalid'])assert.throws(()=>liveOutputGainDb({PIKOO_LIVE_OUTPUT_GAIN_DB:value}));
 assert.equal(liveOutputGainDb({}),0);assert.equal(liveOutputGainDb({PIKOO_LIVE_OUTPUT_GAIN_DB:'4'}),4);
 assert.equal(liveVoice({}),'marin');assert.equal(liveVoice({PIKOO_LIVE_VOICE:'coral'}),'coral');
 assert.equal(liveConfig({voice:'coral'}).audio.output.voice,'coral');
 assert.equal(LIVE_VOICES.length,31);for(const voice of LIVE_VOICES)assert.equal(liveConfig({voice}).audio.output.voice,voice);
 assert.throws(()=>liveConfig({voice:'invented-voice'}),/Unsupported/);
 const instructions=liveConfig().instructions;
 assert(instructions.includes('带笑意'));assert(instructions.includes('附近家人互聊'));
 assert(instructions.includes('Backchannel policy:'));assert(instructions.includes('Interruption policy:'));assert(instructions.includes('自然的日常语速'));assert(!instructions.includes('energetic and animated'));assert(instructions.includes('不要刻意兴奋'));
});
