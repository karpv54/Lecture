// Offline AudioWorklet behavior: no browser permissions, microphones or providers.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../apps/gradio/web/capture.js'),'utf8');
for(const rate of [24000,44100,48000,96000]){
 const frames=[];let Processor;
 const context={sampleRate:rate,AudioWorkletProcessor:class{constructor(){this.port={postMessage:m=>frames.push(m)};}},registerProcessor:(_,c)=>Processor=c,Int16Array,Math,Number};
 vm.runInNewContext(source,context);const p=new Processor();
 p.process([[new Float32Array(128).fill(.5)]]);assert.equal(frames.length,0);
 p.port.onmessage({data:{enabled:true}});
 let remaining=rate*0.8;
 while(remaining>0){const n=Math.min(128,remaining);p.process([[new Float32Array(n).fill(.5)]]);remaining-=n;}
 assert.equal(frames.length,10,'frame duration at '+rate);
 for(const frame of frames){assert.equal(frame.buffer.byteLength,3840);assert.equal(new Int16Array(frame.buffer)[0],16384);assert(Math.abs(frame.level-.5)<1e-7);}
 p.port.onmessage({data:{enabled:false}});p.process([[new Float32Array(1024).fill(1)]]);assert.equal(frames.length,10);
 p.port.onmessage({data:{enabled:true}});assert.equal(p.offset,0);
}
console.log('Audio framing, rate conversion, microphone gating and reset passed at 24/44.1/48/96 kHz.');
