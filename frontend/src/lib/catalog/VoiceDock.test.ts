import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import VoiceDock from './VoiceDock.svelte';
import type { InferResult } from '$lib/api';

// --- mock the voice factory + token fetch ---
interface VoiceMock {
	start: ReturnType<typeof vi.fn>;
	greet: ReturnType<typeof vi.fn>;
	sendInstruction: ReturnType<typeof vi.fn>;
	close: ReturnType<typeof vi.fn>;
	_cbs: { onAgentSpeaking?: (b: boolean) => void };
}
let voiceMock: VoiceMock;
// When true, the next session.start() rejects (simulates a WebRTC error).
let voiceStartRejects = false;
// When true, fetchRealtimeToken() rejects (simulates a 503 / no-key configured).
let tokenFetchRejects = false;

const createVoiceSessionMock = vi.fn((...args: unknown[]) => {
	const cbs = args[1] as { onAgentSpeaking?: (b: boolean) => void };
	voiceMock = {
		start: vi.fn(() =>
			voiceStartRejects
				? Promise.reject(new Error('no realtime token / WebRTC error'))
				: Promise.resolve(undefined)
		),
		greet: vi.fn(),
		sendInstruction: vi.fn(),
		close: vi.fn(),
		_cbs: cbs
	};
	return voiceMock;
});
const fetchTokenMock = vi.fn(async () =>
	tokenFetchRejects
		? Promise.reject(new Error('token unavailable / no key'))
		: { provider: 'openai', client_secret: 'eph', model: 'm', voice: 'alloy' }
);
vi.mock('$lib/voice', () => ({
	createVoiceSession: (...a: unknown[]) => createVoiceSessionMock(...a)
}));
vi.mock('$lib/api', async (orig) => ({
	...((await orig()) as object),
	fetchRealtimeToken: () => fetchTokenMock()
}));

// --- mock EmotionTap ---
interface TapMock {
	start: ReturnType<typeof vi.fn>;
	setAgentSpeaking: ReturnType<typeof vi.fn>;
	abort: ReturnType<typeof vi.fn>;
	close: ReturnType<typeof vi.fn>;
	_cbs: { onDone?: (r: InferResult) => void; onSafetyFlag?: () => void };
}
let tapMock: TapMock;
vi.mock('$lib/emotionTap', () => ({
	EmotionTap: vi.fn().mockImplementation(function (cbs: {
		onDone?: (r: InferResult) => void;
		onSafetyFlag?: () => void;
	}) {
		tapMock = {
			start: vi.fn().mockResolvedValue(undefined),
			setAgentSpeaking: vi.fn(),
			abort: vi.fn(),
			close: vi.fn(),
			_cbs: cbs
		};
		return tapMock;
	})
}));

// --- mock getUserMedia ---
// trackStop is a STABLE reference so teardown assertions are reliable.
let trackStop: ReturnType<typeof vi.fn>;
let fakeStream: MediaStream;
let getUserMedia: ReturnType<typeof vi.fn>;

let onMood: Mock<(infer: InferResult) => void>;

beforeEach(() => {
	vi.useFakeTimers();
	// The Waveform's requestAnimationFrame loop would spin under fake timers; the
	// animation isn't under test here, so make rAF inert.
	vi.stubGlobal('requestAnimationFrame', () => 0);
	vi.stubGlobal('cancelAnimationFrame', () => {});
	voiceStartRejects = false;
	tokenFetchRejects = false;
	onMood = vi.fn<(infer: InferResult) => void>();
	trackStop = vi.fn();
	const track = { stop: trackStop };
	fakeStream = {
		getAudioTracks: () => [track],
		getTracks: () => [track]
	} as unknown as MediaStream;
	getUserMedia = vi.fn().mockResolvedValue(fakeStream);
	// Define only mediaDevices on the real navigator — replacing the whole navigator
	// object breaks @testing-library/user-event (it reads navigator.userAgent/clipboard).
	Object.defineProperty(navigator, 'mediaDevices', {
		configurable: true,
		value: { getUserMedia }
	});
});

afterEach(() => {
	vi.useRealTimers();
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	// @ts-expect-error — remove the mediaDevices stub between tests
	delete navigator.mediaDevices;
});

function setup() {
	return userEvent.setup({
		advanceTimers: vi.advanceTimersByTime.bind(vi),
		pointerEventsCheck: 0
	});
}

async function startRunning(user: ReturnType<typeof userEvent.setup>) {
	render(VoiceDock, { props: { onMood } });
	await user.click(screen.getByRole('button', { name: /find what fits you/i }));
	await waitFor(() => expect(tapMock.start).toHaveBeenCalled());
}

describe('VoiceDock', () => {
	it('shows the idle pill, and "Talk again" when a mood exists', () => {
		const { unmount } = render(VoiceDock, { props: { onMood } });
		expect(screen.getByRole('button', { name: /find what fits you/i })).toBeInTheDocument();
		unmount();
		render(VoiceDock, { props: { onMood, hasMood: true } });
		expect(screen.getByRole('button', { name: /talk again/i })).toBeInTheDocument();
	});

	it('starts both the voice session and EmotionTap on tap, with one processed getUserMedia', async () => {
		const user = setup();
		await startRunning(user);
		expect(voiceMock.start).toHaveBeenCalled();
		expect(tapMock.start).toHaveBeenCalled();
		// The agent opens the conversation.
		expect(voiceMock.greet).toHaveBeenCalled();
		expect(getUserMedia).toHaveBeenCalledTimes(1);
		expect(getUserMedia).toHaveBeenCalledWith({
			audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
		});
	});

	it('wires agent-speaking: voice.onAgentSpeaking → emotionTap.setAgentSpeaking', async () => {
		const user = setup();
		await startRunning(user);
		voiceMock._cbs.onAgentSpeaking?.(true);
		expect(tapMock.setAgentSpeaking).toHaveBeenCalledWith(true);
	});

	const HAPPY_INFER: InferResult = {
		emotion_probs: { happy: 0.8, neutral: 0.2 },
		valence: 0.8,
		arousal: 0.5,
		zone: 'POS_ACTIVE'
	};

	it('happy path: tap.onDone → wrap-up sent; waits for the goodbye, then onMood + collapse + mic stops', async () => {
		const user = setup();
		await startRunning(user);

		tapMock._cbs.onDone?.(HAPPY_INFER);

		await waitFor(() =>
			expect(voiceMock.sendInstruction).toHaveBeenCalledWith(expect.stringContaining('wrap up'))
		);

		// Not done yet — the agent hasn't delivered its closing line.
		expect(onMood).not.toHaveBeenCalled();

		// Agent speaks the goodbye, then finishes.
		await act(() => voiceMock._cbs.onAgentSpeaking?.(true));
		await act(() => voiceMock._cbs.onAgentSpeaking?.(false));
		// After a short quiet period, the wrap-up completes.
		await vi.advanceTimersByTimeAsync(1_000);

		await waitFor(() => expect(onMood).toHaveBeenCalledWith(HAPPY_INFER));
		expect(tapMock.close).toHaveBeenCalled();
		expect(voiceMock.close).toHaveBeenCalled();
		expect(trackStop).toHaveBeenCalled();
		// Collapsed back into the idle pill.
		expect(screen.getByRole('button', { name: /find what fits you/i })).toBeInTheDocument();
	});

	it('wrap-up falls back to the safety cap if the agent never delivers a goodbye', async () => {
		const user = setup();
		await startRunning(user);

		tapMock._cbs.onDone?.(HAPPY_INFER);
		await waitFor(() => expect(voiceMock.sendInstruction).toHaveBeenCalled());

		// No agent speech at all — the ~15 s cap forces the transition so it never hangs.
		expect(onMood).not.toHaveBeenCalled();
		await vi.advanceTimersByTimeAsync(15_000);

		await waitFor(() => expect(onMood).toHaveBeenCalledWith(HAPPY_INFER));
		expect(trackStop).toHaveBeenCalled();
	});

	it('Stop calls tap.abort, stops the mic, and collapses without onMood', async () => {
		const user = setup();
		await startRunning(user);
		await user.click(screen.getByRole('button', { name: /stop/i }));
		expect(tapMock.abort).toHaveBeenCalled();
		expect(onMood).not.toHaveBeenCalled();
		expect(trackStop).toHaveBeenCalled();
		expect(screen.getByRole('button', { name: /find what fits you/i })).toBeInTheDocument();
	});

	it('safety flag shows the crisis card, stops the mic, and Close collapses without onMood', async () => {
		const user = setup();
		await startRunning(user);
		// Flush the reactive update from the out-of-act callback (fake timers prevent
		// waitFor from polling, so drive the Svelte tick directly).
		await act(() => {
			tapMock._cbs.onSafetyFlag?.();
		});
		expect(screen.getAllByText(/crisis|support|helpline|988|reach out/i).length).toBeGreaterThan(0);
		expect(tapMock.close).toHaveBeenCalled();
		expect(trackStop).toHaveBeenCalled();

		await user.click(screen.getByRole('button', { name: /close/i }));
		expect(onMood).not.toHaveBeenCalled();
		expect(screen.getByRole('button', { name: /find what fits you/i })).toBeInTheDocument();
	});

	it('token fetch failure → error panel with Try again, mic stopped, no onMood', async () => {
		tokenFetchRejects = true;
		const user = setup();
		render(VoiceDock, { props: { onMood } });
		await user.click(screen.getByRole('button', { name: /find what fits you/i }));
		await waitFor(() => expect(screen.getByText(/isn't available right now/i)).toBeInTheDocument());
		expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
		expect(trackStop).toHaveBeenCalled();
		expect(onMood).not.toHaveBeenCalled();
	});

	it('voice session start rejection (WebRTC failure after token OK) → error panel, mic stopped', async () => {
		voiceStartRejects = true;
		const user = setup();
		render(VoiceDock, { props: { onMood } });
		await user.click(screen.getByRole('button', { name: /find what fits you/i }));
		await waitFor(() => expect(screen.getByText(/isn't available right now/i)).toBeInTheDocument());
		expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
		expect(trackStop).toHaveBeenCalled();
		expect(onMood).not.toHaveBeenCalled();
	});

	it('shows "Agent is thinking…" after the user goes quiet, until the agent replies', async () => {
		let level = 128; // byte value the fake analyser reports (128 = silence)
		const fakeAnalyser = {
			fftSize: 256,
			getByteTimeDomainData: (arr: Uint8Array) => arr.fill(level)
		};
		vi.stubGlobal(
			'AudioContext',
			class {
				resume() {}
				close() {}
				createMediaStreamSource() {
					return { connect: () => {} };
				}
				createAnalyser() {
					return fakeAnalyser;
				}
			}
		);
		const user = setup();
		await startRunning(user);

		// User speaking (large deviation from the 128 midpoint) → "Listening to you…".
		level = 180;
		await vi.advanceTimersByTimeAsync(300);
		expect(screen.getByText(/listening to you/i)).toBeInTheDocument();

		// User goes quiet → after ~1s of silence the label flips to thinking.
		level = 128;
		await vi.advanceTimersByTimeAsync(1_500);
		expect(screen.getByText(/agent is thinking/i)).toBeInTheDocument();

		// Agent starts replying → speaking label.
		await act(() => voiceMock._cbs.onAgentSpeaking?.(true));
		expect(screen.getByText(/agent is speaking/i)).toBeInTheDocument();

		// Agent finishes; the user hasn't spoken this turn yet → back to listening.
		await act(() => voiceMock._cbs.onAgentSpeaking?.(false));
		await vi.advanceTimersByTimeAsync(300);
		expect(screen.getByText(/listening to you/i)).toBeInTheDocument();
	});

	it('onDestroy releases the mic when the dock unmounts mid-session', async () => {
		const user = setup();
		const { unmount } = render(VoiceDock, { props: { onMood } });
		await user.click(screen.getByRole('button', { name: /find what fits you/i }));
		await waitFor(() => expect(tapMock.start).toHaveBeenCalled());
		unmount();
		expect(trackStop).toHaveBeenCalled();
	});
});
