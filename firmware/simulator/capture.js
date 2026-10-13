class Capture extends AudioWorkletProcessor {
  constructor(){super();this.samples=new Int16Array(320);this.used=0;}
  process(inputs){const ch=inputs[0]?.[0];if(ch)for(const x of ch){this.samples[this.used++]=Math.max(-32768,Math.min(32767,Math.round(x*32767)));if(this.used===320){this.port.postMessage(this.samples.buffer.slice(0));this.used=0;}}return true;}
}
registerProcessor('capture',Capture);
