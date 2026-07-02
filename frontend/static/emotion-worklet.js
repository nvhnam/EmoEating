/**
 * AudioWorkletProcessor: downmix → resample to 16 kHz → post Int16 PCM frames.
 * Accumulates samples until FRAME_SAMPLES is reached, then posts as a
 * transferable ArrayBuffer. `sampleRate` is available as a worklet global.
 */
const TARGET_RATE = 16_000;
const FRAME_SAMPLES = 1_600; // 100 ms at 16 kHz

class EmotionProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    /** @type {Float32Array} */
    this._buf = new Float32Array(0);
  }

  /** @param {Float32Array[][]} inputs */
  process(inputs) {
    const input = inputs[0];
    if (!input || !input.length) return true;

    // Downmix to mono
    const nCh = input.length;
    const nFrames = input[0].length;
    const mono = new Float32Array(nFrames);
    for (let i = 0; i < nFrames; i++) {
      let s = 0;
      for (let c = 0; c < nCh; c++) s += input[c][i];
      mono[i] = s / nCh;
    }

    // Resample to 16 kHz (linear interp; sampleRate is the worklet global)
    const ratio = sampleRate / TARGET_RATE;
    const outLen = Math.round(mono.length / ratio);
    const resampled = new Float32Array(outLen);
    for (let i = 0; i < outLen; i++) {
      const pos = i * ratio;
      const lo = Math.floor(pos);
      const hi = Math.min(lo + 1, mono.length - 1);
      const frac = pos - lo;
      resampled[i] = mono[lo] * (1 - frac) + mono[hi] * frac;
    }

    // Accumulate and emit FRAME_SAMPLES-sized Int16 chunks
    const merged = new Float32Array(this._buf.length + resampled.length);
    merged.set(this._buf);
    merged.set(resampled, this._buf.length);
    this._buf = merged;

    while (this._buf.length >= FRAME_SAMPLES) {
      const chunk = this._buf.slice(0, FRAME_SAMPLES);
      this._buf = this._buf.slice(FRAME_SAMPLES);
      const i16 = new Int16Array(FRAME_SAMPLES);
      for (let i = 0; i < FRAME_SAMPLES; i++) {
        const s = Math.max(-1, Math.min(1, chunk[i]));
        i16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      this.port.postMessage(i16.buffer, [i16.buffer]);
    }

    return true; // keep processor alive
  }
}

registerProcessor('emotion-processor', EmotionProcessor);
