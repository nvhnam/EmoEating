<script lang="ts">
	import { onDestroy } from 'svelte';

	// Animated frequency bars driven by a Web Audio AnalyserNode, with a progress line.
	// `analyser` may be null (nothing to show yet); honors prefers-reduced-motion.
	let {
		analyser = null,
		progress = 0,
		label = ''
	}: { analyser?: AnalyserNode | null; progress?: number; label?: string } = $props();

	let canvas = $state<HTMLCanvasElement | null>(null);
	let raf = 0;

	const reduceMotion =
		typeof window !== 'undefined' &&
		!!window.matchMedia &&
		window.matchMedia('(prefers-reduced-motion: reduce)').matches;

	const BARS = 48;

	function render(level: (i: number) => number) {
		const c = canvas;
		if (!c) return;
		const ctx = c.getContext('2d');
		if (!ctx) return;
		const w = c.width;
		const h = c.height;
		ctx.clearRect(0, 0, w, h);
		ctx.fillStyle = getComputedStyle(c).color || '#000';
		const bw = w / BARS;
		for (let i = 0; i < BARS; i++) {
			const bh = Math.max(2, Math.min(1, level(i)) * h);
			ctx.fillRect(i * bw + bw * 0.2, (h - bh) / 2, bw * 0.6, bh);
		}
	}

	function loop() {
		raf = requestAnimationFrame(loop);
		if (!analyser) {
			render(() => 0.03);
			return;
		}
		const data = new Uint8Array(analyser.frequencyBinCount);
		analyser.getByteFrequencyData(data);
		const step = Math.max(1, Math.floor(data.length / BARS));
		render((i) => (data[i * step] ?? 0) / 255);
	}

	$effect(() => {
		// Touch `analyser` so the effect re-runs when it appears/disappears.
		const a = analyser;
		cancelAnimationFrame(raf);
		if (!canvas) return;
		if (reduceMotion) {
			// Static: a flat baseline that still reflects presence, no animation.
			render(() => (a ? 0.12 : 0.03));
			return;
		}
		loop();
		return () => cancelAnimationFrame(raf);
	});

	onDestroy(() => cancelAnimationFrame(raf));
</script>

<div class="space-y-3">
	{#if label}
		<p class="text-sm font-medium text-muted-foreground" aria-live="polite">{label}</p>
	{/if}
	<canvas
		bind:this={canvas}
		width="480"
		height="72"
		class="h-16 w-full text-primary/80"
		aria-hidden="true"
	></canvas>
	<div class="h-1 w-full overflow-hidden rounded-full bg-muted">
		<div
			class="h-full rounded-full bg-primary transition-all duration-700"
			style="width: {progress}%"
		></div>
	</div>
</div>
