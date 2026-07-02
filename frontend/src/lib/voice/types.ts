export interface VoiceSession {
	start(stream: MediaStream): Promise<void>;
	// Trigger the agent's opening turn (warm greeting + first question). Safe to call
	// right after start() — each impl waits for its transport to be ready.
	greet(): void;
	sendInstruction(text: string): void;
	close(): void;
}

export interface VoiceSessionCallbacks {
	onAgentSpeaking?: (speaking: boolean) => void;
	// Emitted once when the agent's audio output stream is available, so the UI can
	// visualize the agent's voice (e.g. a waveform). Best-effort — may never fire.
	onAgentStream?: (stream: MediaStream) => void;
}
