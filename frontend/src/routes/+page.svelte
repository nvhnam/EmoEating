<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { Button } from '$lib/components/ui/button';
	import { fetchVoiceConfig } from '$lib/api';
	import { consentGiven, voiceConsentGiven } from '$lib/stores/session';

	let agreed = $state(false);
	let providerName = $state('our voice AI provider');

	onMount(async () => {
		try {
			providerName = (await fetchVoiceConfig()).provider_name;
		} catch {
			/* keep neutral fallback */
		}
	});

	function getStarted() {
		// Single consent for the whole flow (it leads into the voice conversation).
		consentGiven.set(true);
		voiceConsentGiven.set(true);
		goto('/app');
	}
</script>

<section class="mx-auto max-w-xl space-y-6 text-center">
	<h1 class="text-4xl font-bold tracking-tight">EmoEating</h1>
	<p class="text-lg text-muted-foreground">
		Chat with EmoEating about your day. We read the emotion in <em>how</em> you sound — not what you say
		— and recommend food that fits your mood, showing our work: the detected mood, the probabilities,
		and the nutrient targets behind every pick.
	</p>

	<div class="space-y-3 rounded-md border bg-muted/40 p-4 text-left text-sm">
		<p class="font-medium">Before you start</p>
		<p class="text-muted-foreground">
			Your voice is streamed to <strong>{providerName}</strong> and is processed under their data
			policy, which may include
			<strong>short-term retention for safety monitoring</strong>. We do not store your audio,
			transcript, or emotion data — the emotion read runs on our server in memory and is discarded
			after your session.
		</p>
		<label class="flex cursor-pointer items-start gap-3">
			<input type="checkbox" class="mt-0.5 shrink-0" bind:checked={agreed} />
			<span class="text-muted-foreground">
				I understand this is for general wellbeing and is <strong>not a clinical tool</strong> — not a
				substitute for medical or mental-health care — and I agree to the audio processing described
				above.
			</span>
		</label>
	</div>

	<Button size="lg" onclick={getStarted} disabled={!agreed}>Get started</Button>
</section>
