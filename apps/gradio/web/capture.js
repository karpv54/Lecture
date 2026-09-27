// Resample any browser audio rate into 80 ms frames of 24 kHz mono PCM16.
// A weighted area average preserves frame duration across 44.1/48/96 kHz devices.
class TutorCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.enabled = false;
    this.ratio = sampleRate / 24000;
    this.reset();
    this.port.onmessage = ({data}) => { this.enabled = data.enabled === true; this.reset(); };
  }
  reset() {
    this.frame = new Int16Array(1920);
    this.offset = 0; this.energy = 0;
    this.area = 0; this.filled = 0;
  }
  output(value) {
    this.frame[this.offset++] = Math.round(value * (value < 0 ? 32768 : 32767));
    this.energy += value * value;
    if (this.offset === 1920) {
      const buffer = this.frame.buffer;
      this.port.postMessage({buffer, level: Math.sqrt(this.energy / 1920)}, [buffer]);
      this.frame = new Int16Array(1920); this.offset = 0; this.energy = 0;
    }
  }
  process(inputs) {
    const channel = inputs[0]?.[0];
    if (!channel || !this.enabled) return true;
    for (const sample of channel) {
      const value = Math.max(-1, Math.min(1, Number.isFinite(sample) ? sample : 0));
      let remaining = 1;
      while (remaining > 1e-9) {
        const take = Math.min(remaining, this.ratio - this.filled);
        this.area += value * take;
        this.filled += take;
        remaining -= take;
        if (this.filled >= this.ratio - 1e-9) {
          this.output(this.area / this.ratio);
          this.area = 0; this.filled = 0;
        }
      }
    }
    return true;
  }
}
registerProcessor("tutor-capture", TutorCapture);
