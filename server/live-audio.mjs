// Stateful 3:2 interpolation; preserves phase across arbitrary PCM packet boundaries.
export class Pcm16To24 {
  constructor(){this.reset();}
  reset(){this.samples=[];this.phase=0;}
  append(bytes) {
    if(bytes.length%2)throw new Error('PCM16 byte count must be even');
    for(let i=0;i<bytes.length;i+=2)this.samples.push(bytes.readInt16LE(i));
    const out=[];
    while(Math.floor(this.phase/3)+1<this.samples.length){
      const i=Math.floor(this.phase/3),fraction=(this.phase%3)/3;
      out.push(Math.round(this.samples[i]*(1-fraction)+this.samples[i+1]*fraction));this.phase+=2;
    }
    const consumed=Math.floor(this.phase/3);this.samples.splice(0,consumed);this.phase-=consumed*3;
    const result=Buffer.alloc(out.length*2);out.forEach((v,i)=>result.writeInt16LE(v,i*2));return result;
  }
}
export function pcmRms(bytes) {
  let sum=0;for(let i=0;i+1<bytes.length;i+=2){const x=bytes.readInt16LE(i)/32768;sum+=x*x;}
  return Math.sqrt(sum/Math.max(1,bytes.length/2));
}

export function liveOutputGainDb(env=process.env) {
  const db=Number(env.PIKOO_LIVE_OUTPUT_GAIN_DB??0);
  if(!Number.isFinite(db)||db<0||db>12)throw new Error('PIKOO_LIVE_OUTPUT_GAIN_DB must be between 0 and 12');
  return db;
}

// Memoryless, sample-local soft knee: no lookahead, packet-boundary envelope
// jumps, extra buffering or hard PCM clipping. Quiet samples get the full gain.
export class PcmOutputGain {
  constructor(db=0) {
    this.db=liveOutputGainDb({PIKOO_LIVE_OUTPUT_GAIN_DB:db});
    this.scale=10**(this.db/20);this.limitedSamples=0;
    this.inputPower=0;this.outputPower=0;this.samples=0;this.maxInputRms=0;this.maxOutputRms=0;
  }
  append(bytes) {
    if(bytes.length%2)throw new Error('PCM16 byte count must be even');
    if(!this.db)return bytes;
    const out=Buffer.alloc(bytes.length),knee=.75,ceiling=.94;let inputPower=0,outputPower=0;
    for(let i=0;i<bytes.length;i+=2) {
      const value=bytes.readInt16LE(i)/32768*this.scale,amplitude=Math.abs(value);
      const limited=amplitude>knee?knee+(ceiling-knee)*Math.tanh((amplitude-knee)/(ceiling-knee)):amplitude;
      if(amplitude>knee)this.limitedSamples++;
      const sample=Math.round(Math.sign(value)*limited*32768);
      inputPower+=(bytes.readInt16LE(i)/32768)**2;outputPower+=(sample/32768)**2;
      out.writeInt16LE(sample,i);
    }
    this.samples+=bytes.length/2;this.inputPower+=inputPower;this.outputPower+=outputPower;
    this.maxInputRms=Math.max(this.maxInputRms,Math.sqrt(inputPower/Math.max(1,bytes.length/2)));
    this.maxOutputRms=Math.max(this.maxOutputRms,Math.sqrt(outputPower/Math.max(1,bytes.length/2)));
    return out;
  }
  stats() {return {measuredGainDb:this.inputPower?10*Math.log10(this.outputPower/this.inputPower):null,maxSourceRms:this.maxInputRms,maxDeliveredRms:this.maxOutputRms};}
}
