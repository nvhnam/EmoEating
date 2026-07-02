import { describe, it, expect, vi } from 'vitest';
import { encodeWav, audioBlobToWav } from './wav';

function ascii(view: DataView, offset: number, len: number): string {
	let s = '';
	for (let i = 0; i < len; i++) s += String.fromCharCode(view.getUint8(offset + i));
	return s;
}

describe('encodeWav', () => {
	it('writes a valid mono 16-bit PCM WAV header', async () => {
		const samples = new Float32Array([0, 0.5, -0.5, 1, -1]);
		const blob = encodeWav(samples, 16000);
		expect(blob.type).toBe('audio/wav');
		const view = new DataView(await blob.arrayBuffer());

		expect(ascii(view, 0, 4)).toBe('RIFF');
		expect(ascii(view, 8, 4)).toBe('WAVE');
		expect(ascii(view, 12, 4)).toBe('fmt ');
		expect(ascii(view, 36, 4)).toBe('data');
		expect(view.getUint16(20, true)).toBe(1); // PCM
		expect(view.getUint16(22, true)).toBe(1); // mono
		expect(view.getUint32(24, true)).toBe(16000); // sample rate
		expect(view.getUint16(34, true)).toBe(16); // bits per sample
		// total length = 44-byte header + 2 bytes per sample
		expect(view.byteLength).toBe(44 + samples.length * 2);
		expect(view.getUint32(40, true)).toBe(samples.length * 2); // data chunk size
	});

	it('clamps and scales samples to 16-bit range', async () => {
		const view = new DataView(await encodeWav(new Float32Array([1, -1, 2, -2]), 8000).arrayBuffer());
		// +1 -> 32767, -1 -> -32768, and out-of-range clamps the same way
		expect(view.getInt16(44, true)).toBe(32767);
		expect(view.getInt16(46, true)).toBe(-32768);
		expect(view.getInt16(48, true)).toBe(32767); // clamped from 2
		expect(view.getInt16(50, true)).toBe(-32768); // clamped from -2
	});
});

describe('audioBlobToWav', () => {
	it('decodes via AudioContext, downmixes to mono, and re-encodes WAV', async () => {
		const left = new Float32Array([0.25, 0.25]);
		const right = new Float32Array([0.75, 0.75]);
		const fakeAudio = {
			numberOfChannels: 2,
			length: 2,
			sampleRate: 16000,
			getChannelData: (c: number) => (c === 0 ? left : right)
		};
		const close = vi.fn();
		class FakeCtx {
			decodeAudioData = vi.fn(async () => fakeAudio);
			close = close;
		}
		vi.stubGlobal('window', { AudioContext: FakeCtx });

		const wav = await audioBlobToWav(new Blob([new Uint8Array([1, 2, 3])]));
		expect(wav.type).toBe('audio/wav');
		const view = new DataView(await wav.arrayBuffer());
		expect(ascii(view, 0, 4)).toBe('RIFF');
		expect(view.getUint32(24, true)).toBe(16000);
		// downmix average of 0.25 and 0.75 = 0.5 -> ~16383
		expect(view.getInt16(44, true)).toBeCloseTo(Math.round(0.5 * 0x7fff), -1);
		expect(close).toHaveBeenCalled();
		vi.unstubAllGlobals();
	});
});
