import { describe, it, expect } from 'vitest';
import {
  TARGET_SAMPLE_RATE,
  downmixToMono,
  resample,
  floatToInt16,
  toInt16PCM16k
} from './pcm';

describe('downmixToMono', () => {
  it('passes through mono unchanged', () => {
    const m = new Float32Array([0.1, 0.2, 0.3]);
    expect(downmixToMono(m, 1)).toBe(m);
  });

  it('averages two channels from interleaved data', () => {
    // interleaved L/R: [L0, R0, L1, R1]
    const stereo = new Float32Array([0.6, 0.2, -0.4, 0.4]);
    const mono = downmixToMono(stereo, 2);
    expect(mono[0]).toBeCloseTo(0.4);
    expect(mono[1]).toBeCloseTo(0.0);
  });
});

describe('resample', () => {
  it('48k→16k produces ~1/3 length', () => {
    const src = new Float32Array(4800); // 100 ms at 48 kHz
    const out = resample(src, 48_000);
    expect(out.length).toBe(Math.round(4800 / 3)); // 1600
  });

  it('returns input unchanged when srcRate equals TARGET_SAMPLE_RATE', () => {
    const src = new Float32Array([0.1, 0.2]);
    expect(resample(src, TARGET_SAMPLE_RATE)).toBe(src);
  });

  it('preserves a 440 Hz sine shape after resampling', () => {
    const srcRate = 48_000;
    const freq = 440;
    const src = new Float32Array(srcRate);
    for (let i = 0; i < srcRate; i++)
      src[i] = Math.sin((2 * Math.PI * freq * i) / srcRate);
    const out = resample(src, srcRate);
    expect(out.length).toBe(TARGET_SAMPLE_RATE);
    // Spot-check 1 ms into the output
    const t = 0.001;
    const idx = Math.round(t * TARGET_SAMPLE_RATE);
    expect(out[idx]).toBeCloseTo(Math.sin(2 * Math.PI * freq * t), 1);
  });
});

describe('floatToInt16', () => {
  it('maps +1 to 0x7fff and -1 to -0x8000', () => {
    const f = new Float32Array([1.0, -1.0, 0.0]);
    const i = floatToInt16(f);
    expect(i[0]).toBe(0x7fff);
    expect(i[1]).toBe(-0x8000);
    expect(i[2]).toBe(0);
  });

  it('clamps values outside [-1, 1]', () => {
    const f = new Float32Array([2.0, -3.0]);
    const i = floatToInt16(f);
    expect(i[0]).toBe(0x7fff);
    expect(i[1]).toBe(-0x8000);
  });
});

describe('toInt16PCM16k', () => {
  it('48k input → Int16Array with TARGET_SAMPLE_RATE length', () => {
    const input = new Float32Array(48_000);
    const out = toInt16PCM16k(input, 48_000);
    expect(out).toBeInstanceOf(Int16Array);
    expect(out.length).toBe(TARGET_SAMPLE_RATE);
  });

  it('encodes a 440Hz sine end-to-end (non-zero, in range)', () => {
    const input = new Float32Array(48_000);
    for (let i = 0; i < 48_000; i++) {
      input[i] = Math.sin((2 * Math.PI * 440 * i) / 48_000);
    }
    const out = toInt16PCM16k(input, 48_000);
    expect(out.length).toBe(TARGET_SAMPLE_RATE);
    const arr = Array.from(out);
    expect(Math.max(...arr)).toBeLessThanOrEqual(0x7fff);
    expect(Math.min(...arr)).toBeGreaterThanOrEqual(-0x8000);
    // proves real value path, not all-zeros:
    expect(Math.max(...arr)).toBeGreaterThan(10000);
    expect(Math.min(...arr)).toBeLessThan(-10000);
  });
});
