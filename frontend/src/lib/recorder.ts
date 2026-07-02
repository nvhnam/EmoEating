export class AudioRecorder {
	private mediaRecorder: MediaRecorder | null = null;
	private chunks: Blob[] = [];
	recording = false;

	async start(): Promise<void> {
		// Guard against a double-start orphaning the previous stream's tracks.
		if (this.recording) return;
		const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
		this.chunks = [];
		this.mediaRecorder = new MediaRecorder(stream);
		this.mediaRecorder.ondataavailable = (e) => {
			if (e.data && e.data.size > 0) this.chunks.push(e.data);
		};
		this.mediaRecorder.start();
		this.recording = true;
	}

	stop(): Promise<Blob> {
		return new Promise((resolve, reject) => {
			const mr = this.mediaRecorder;
			if (!mr) {
				reject(new Error('not recording'));
				return;
			}
			mr.onstop = () => {
				mr.stream.getTracks().forEach((t) => t.stop());
				this.recording = false;
				resolve(new Blob(this.chunks, { type: mr.mimeType || 'audio/webm' }));
			};
			mr.stop();
		});
	}
}
