<script lang="ts">
	import { onDestroy } from 'svelte';
	import { Button } from '$lib/components/ui/button';
	import { EmotionTap } from '$lib/emotionTap';
	import { createVoiceSession } from '$lib/voice';
	import type { VoiceSession } from '$lib/voice/types';
	import { fetchRealtimeToken } from '$lib/api';
	import type { InferResult } from '$lib/api';
	import Waveform from '$lib/components/Waveform.svelte';

	// The dock never navigates: done, abort, and safety all resolve back to the pill.
	let {
		hasMood = false,
		onMood
	}: {
		hasMood?: boolean;
		onMood: (infer: InferResult) => void;
	} = $props();

	type Sub = 'idle' | 'connecting' | 'running' | 'done' | 'safety';
	let sub = $state<Sub>('idle');
	let agentSpeaking = $state(false);
	let progress = $state(0); // 0–100, speech collected toward the 18 s floor — NOT emotion
	let errorMsg = $state<string | null>(null);
	const expanded = $derived(sub !== 'idle' || errorMsg !== null);

	// Turn-state heuristic for the waveform label: once the user has spoken this
	// turn and then gone quiet (and the agent isn't audible yet), the gap is the
	// model generating its reply — show "thinking" instead of "listening".
	const THINK_QUIET_MS = 1_000;
	const VOICE_RMS_BYTES = 4; // deviation from the 128 midpoint that counts as voice
	let agentThinking = $state(false);
	let userSpokeThisTurn = false;
	let lastVoiceAt = 0;
	let monitorId: ReturnType<typeof setInterval> | null = null;
	const waveLabel = $derived(
		agentSpeaking ? 'Agent is speaking…' : agentThinking ? 'Agent is thinking…' : 'Listening to you…'
	);

	function micLevel(): number {
		if (!micAnalyser) return 0;
		const buf = new Uint8Array(micAnalyser.fftSize);
		micAnalyser.getByteTimeDomainData(buf);
		let sum = 0;
		for (let i = 0; i < buf.length; i++) {
			const d = buf[i] - 128;
			sum += d * d;
		}
		return Math.sqrt(sum / buf.length);
	}

	function monitorTick(): void {
		if (agentSpeaking) return; // reset happens on the speaking signal itself
		const now = Date.now();
		if (micLevel() >= VOICE_RMS_BYTES) {
			userSpokeThisTurn = true;
			lastVoiceAt = now;
			agentThinking = false;
			return;
		}
		if (userSpokeThisTurn && now - lastVoiceAt >= THINK_QUIET_MS) agentThinking = true;
	}

	// Live objects (not reactive).
	let session: VoiceSession | null = null;
	let tap: EmotionTap | null = null;
	let stream: MediaStream | null = null;

	// Visualization (best-effort): analysers on the mic and the agent output. The
	// waveform shows whichever side is currently speaking.
	let vizCtx: AudioContext | null = null;
	let micAnalyser = $state<AnalyserNode | null>(null);
	let agentAnalyser = $state<AnalyserNode | null>(null);
	const activeAnalyser = $derived(agentSpeaking && agentAnalyser ? agentAnalyser : micAnalyser);

	function analyserFor(s: MediaStream): AnalyserNode | null {
		try {
			if (!vizCtx) {
				vizCtx = new AudioContext();
				void vizCtx.resume?.();
			}
			const src = vizCtx.createMediaStreamSource(s);
			const an = vizCtx.createAnalyser();
			an.fftSize = 256;
			src.connect(an);
			return an;
		} catch {
			return null; // visualization is non-essential
		}
	}

	// This component OWNS the mic stream — EmotionTap and the VoiceSession only borrow
	// it. Stop the tracks on every teardown path; unmounting fires onDestroy → cleanup,
	// so leaving the page always releases the mic.
	function cleanup(): void {
		if (monitorId !== null) {
			clearInterval(monitorId);
			monitorId = null;
		}
		agentThinking = false;
		userSpokeThisTurn = false;
		tap?.close();
		session?.close();
		stream?.getTracks().forEach((t) => t.stop());
		micAnalyser = null;
		agentAnalyser = null;
		void vizCtx?.close?.();
		vizCtx = null;
		tap = null;
		session = null;
		stream = null;
	}

	// Wrap-up: after the emotion read is confident, let the agent deliver its closing
	// line and wait for it to actually finish (agent-speaking goes quiet) before leaving,
	// capped so it can never hang. Driven by the onAgentSpeaking signal via wrapTick.
	let wrapTick: ((speaking: boolean) => void) | null = null;

	function waitForAgentGoodbye(capMs: number): Promise<void> {
		return new Promise((resolve) => {
			let settled = false;
			let sawSpeech = agentSpeaking;
			let quiet: ReturnType<typeof setTimeout> | null = null;
			const QUIET_MS = 1_000;
			const finish = () => {
				if (settled) return;
				settled = true;
				if (quiet) clearTimeout(quiet);
				clearTimeout(cap);
				wrapTick = null;
				resolve();
			};
			const cap = setTimeout(finish, capMs);
			wrapTick = (speaking: boolean) => {
				if (speaking) {
					sawSpeech = true;
					if (quiet) {
						clearTimeout(quiet);
						quiet = null;
					}
				} else if (sawSpeech) {
					quiet = setTimeout(finish, QUIET_MS);
				}
			};
		});
	}

	async function handleDone(infer: InferResult): Promise<void> {
		sub = 'done';
		session?.sendInstruction(
			'The emotion analysis is complete. Please wrap up our conversation warmly in one or two sentences and say goodbye.'
		);
		await waitForAgentGoodbye(15_000);
		cleanup();
		sub = 'idle';
		onMood(infer);
	}

	function handleSafetyFlag(): void {
		sub = 'safety';
		cleanup();
	}

	function handleAbort(): void {
		tap?.abort();
		cleanup();
		sub = 'idle';
	}

	function dismiss(): void {
		errorMsg = null;
		sub = 'idle';
	}

	async function startSession(): Promise<void> {
		errorMsg = null;
		sub = 'connecting';
		try {
			stream = await navigator.mediaDevices.getUserMedia({
				audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
			});
		} catch {
			errorMsg = 'Microphone access was denied. Please allow access and try again.';
			sub = 'idle';
			return;
		}

		micAnalyser = analyserFor(stream);

		tap = new EmotionTap({
			onTick: ({ elapsed }) => {
				progress = Math.min((elapsed / 18) * 100, 100);
			},
			onDone: handleDone,
			onSafetyFlag: handleSafetyFlag
		});

		try {
			const token = await fetchRealtimeToken();
			session = createVoiceSession(token, {
				onAgentSpeaking: (speaking) => {
					agentSpeaking = speaking;
					if (speaking) {
						// A new agent turn resets the cycle: the next quiet gap is the
						// user's turn to answer, not the model thinking.
						agentThinking = false;
						userSpokeThisTurn = false;
					}
					tap?.setAgentSpeaking(speaking);
					wrapTick?.(speaking);
				},
				onAgentStream: (s) => {
					agentAnalyser = analyserFor(s);
				}
			});
			await Promise.all([tap.start(stream), session.start(stream)]);
			sub = 'running';
			monitorId = setInterval(monitorTick, 150);
			// The agent opens the conversation (greeting + first question).
			session.greet();
		} catch {
			errorMsg =
				"Live conversation isn't available right now. Check that the voice provider key is configured, then try again.";
			cleanup();
			sub = 'idle';
		}
	}

	onDestroy(() => cleanup());
</script>

<div class="pointer-events-none fixed inset-x-0 bottom-0 z-40 px-4 pb-[max(env(safe-area-inset-bottom),1rem)]">
	{#if !expanded}
		<button
			type="button"
			class="pointer-events-auto mx-auto flex w-full max-w-md items-center justify-center gap-2 rounded-full bg-primary px-6 py-3.5 font-medium text-primary-foreground shadow-lg"
			onclick={startSession}
		>
			<span aria-hidden="true">🎙</span>
			{hasMood ? 'Talk again' : 'Find what fits you'}
		</button>
	{:else}
		<div
			class="pointer-events-auto mx-auto w-full max-w-md space-y-4 rounded-2xl border bg-background p-4 shadow-xl"
		>
			{#if sub === 'safety'}
				<div class="space-y-3 rounded-md border border-destructive/40 bg-destructive/10 p-4">
					<p class="font-semibold text-destructive">Let's pause here</p>
					<p class="text-sm text-muted-foreground">
						If you're in distress, please reach out for support. In the US you can call or text
						<strong>988</strong> (Suicide &amp; Crisis Lifeline) any time. Crisis helplines are
						available worldwide — you don't have to navigate this alone.
					</p>
					<Button variant="outline" onclick={dismiss}>Close</Button>
				</div>
			{:else if errorMsg}
				<p class="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{errorMsg}</p>
				<div class="flex gap-2">
					<Button size="sm" onclick={startSession}>Try again</Button>
					<Button size="sm" variant="ghost" onclick={dismiss}>Close</Button>
				</div>
			{:else if sub === 'connecting'}
				<div class="flex items-center gap-3 text-sm text-muted-foreground">
					<span
						class="size-4 rounded-full border-2 border-muted-foreground/30 border-t-primary motion-safe:animate-spin"
						aria-hidden="true"
					></span>
					<span aria-live="polite">Connecting…</span>
				</div>
			{:else}
				<Waveform analyser={activeAnalyser} {progress} label={waveLabel} />
				{#if sub === 'running'}
					<Button variant="destructive" size="sm" onclick={handleAbort}>Stop</Button>
				{:else}
					<p class="text-sm text-muted-foreground">Wrapping up…</p>
				{/if}
			{/if}
		</div>
	{/if}
</div>
