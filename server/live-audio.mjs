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
