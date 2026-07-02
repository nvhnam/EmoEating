/**
 * Pure PCM helpers shared between the AudioWorklet and unit tests.
 * Reuses the Float32→Int16 conversion pattern from wav.ts.
 */

export const TARGET_SAMPLE_RATE = 16_000;

/** Average all channels (interleaved) into a mono Float32 track. */
export function downmixToMono(data: Float32Array, channels: number): Float32Array {
  if (channels === 1) return data;
  const frames = data.length / channels;
  const mono = new Float32Array(frames);
  for (let i = 0; i < frames; i++) {
    let sum = 0;
    for (let c = 0; c < channels; c++) sum += data[i * channels + c];
    mono[i] = sum / channels;
  }
  return mono;
}

/** Linear-interpolation resample from `srcRate` to TARGET_SAMPLE_RATE. */
export function resample(input: Float32Array, srcRate: number): Float32Array {
  if (srcRate === TARGET_SAMPLE_RATE) return input;
  const ratio = srcRate / TARGET_SAMPLE_RATE;
  const outLen = Math.round(input.length / ratio);
  const out = new Float32Array(outLen);
  for (let i = 0; i < outLen; i++) {
    const pos = i * ratio;
    const lo = Math.floor(pos);
    const hi = Math.min(lo + 1, input.length - 1);
    const frac = pos - lo;
    out[i] = input[lo] * (1 - frac) + input[hi] * frac;
  }
  return out;
}

/** Clamp Float32 samples and convert to Int16 PCM (matches wav.ts encodeWav). */
export function floatToInt16(input: Float32Array): Int16Array {
  // JS typed arrays are native-endian; little-endian on all real browser/server targets (matches the backend's Int16 LE expectation).
  const out = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

/** Convenience: mono Float32 at srcRate → Int16 at 16 kHz. */
export function toInt16PCM16k(input: Float32Array, srcRate: number): Int16Array {
  return floatToInt16(resample(input, srcRate));
}
