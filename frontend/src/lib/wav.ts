/**
 * Audio → WAV conversion done in the browser.
 *
 * The backend decodes uploads with libsndfile (WAV/FLAC/...), which cannot read
 * the webm/opus that `MediaRecorder` produces. The browser, however, can decode
 * its own recording (and most upload formats) via `AudioContext.decodeAudioData`.
 * So we decode to PCM client-side and re-encode a mono 16-bit WAV that the
 * backend reads natively. The backend still resamples to 16 kHz and validates
 * the 3–5 s duration, so we encode at the decoded sample rate unchanged.
 */

/** Encode mono float samples as a 16-bit PCM WAV blob. */
export function encodeWav(samples: Float32Array, sampleRate: number): Blob {
	const bytesPerSample = 2; // 16-bit
	const dataSize = samples.length * bytesPerSample;
	const buffer = new ArrayBuffer(44 + dataSize);
	const view = new DataView(buffer);

	let off = 0;
	const writeStr = (s: string) => {
		for (let i = 0; i < s.length; i++) view.setUint8(off++, s.charCodeAt(i));
	};

	writeStr('RIFF');
	view.setUint32(off, 36 + dataSize, true);
	off += 4;
	writeStr('WAVE');
	writeStr('fmt ');
	view.setUint32(off, 16, true); // fmt chunk size
	off += 4;
	view.setUint16(off, 1, true); // PCM
	off += 2;
	view.setUint16(off, 1, true); // mono
	off += 2;
	view.setUint32(off, sampleRate, true);
	off += 4;
	view.setUint32(off, sampleRate * bytesPerSample, true); // byte rate (mono)
	off += 4;
	view.setUint16(off, bytesPerSample, true); // block align
	off += 2;
	view.setUint16(off, 16, true); // bits per sample
	off += 2;
	writeStr('data');
	view.setUint32(off, dataSize, true);
	off += 4;

	for (let i = 0; i < samples.length; i++) {
		const s = Math.max(-1, Math.min(1, samples[i]));
		view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true);
		off += 2;
	}

	return new Blob([view], { type: 'audio/wav' });
}

/** Average all channels into a single mono track. */
function downmix(audio: AudioBuffer): Float32Array {
	if (audio.numberOfChannels === 1) return audio.getChannelData(0);
	const out = new Float32Array(audio.length);
	for (let c = 0; c < audio.numberOfChannels; c++) {
		const data = audio.getChannelData(c);
		for (let i = 0; i < audio.length; i++) out[i] += data[i] / audio.numberOfChannels;
	}
	return out;
}

/** Decode any browser-supported audio blob and re-encode it as a mono WAV. */
export async function audioBlobToWav(blob: Blob): Promise<Blob> {
	const arrayBuffer = await blob.arrayBuffer();
	const Ctx: typeof AudioContext =
		window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
	const ctx = new Ctx();
	try {
		const audio = await ctx.decodeAudioData(arrayBuffer);
		return encodeWav(downmix(audio), audio.sampleRate);
	} finally {
		void ctx.close();
	}
}
