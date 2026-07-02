<script lang="ts">
	import { onMount } from 'svelte';
	import { get } from 'svelte/store';
	import { goto } from '$app/navigation';
	import { Button } from '$lib/components/ui/button';
	import { consentGiven, inference, mealType, profile } from '$lib/stores/session';
	import { fetchFoods, recommend } from '$lib/api';
	import type { FoodOut, InferResult, RecommendResult } from '$lib/api';
	import { deriveOrder, type CatalogEntry } from '$lib/catalog/ordering';
	import CatalogHeader from '$lib/catalog/CatalogHeader.svelte';
	import CatalogGrid from '$lib/catalog/CatalogGrid.svelte';
	import ProfileSheet from '$lib/catalog/ProfileSheet.svelte';
	import DishSheet from '$lib/catalog/DishSheet.svelte';
	import VoiceDock from '$lib/catalog/VoiceDock.svelte';
	import TransparencyPanel from '$lib/components/TransparencyPanel.svelte';

	let catalog = $state<FoodOut[]>([]);
	let catalogError = $state(false);
	let recommendation = $state<RecommendResult | null>(null);
	let recError = $state(false);
	let mood = $state<InferResult | null>(null);

	let profileOpen = $state(false);
	let selected = $state<CatalogEntry | null>(null);

	const entries = $derived(deriveOrder(catalog, recommendation));

	async function loadCatalog(): Promise<void> {
		catalogError = false;
		try {
			catalog = await fetchFoods();
		} catch {
			catalogError = true;
		}
	}

	async function refreshRecommendation(): Promise<void> {
		const inf = get(inference);
		if (!inf) return;
		recError = false;
		try {
			recommendation = await recommend({
				zone: inf.zone,
				profile: get(profile) ?? undefined,
				meal_type: get(mealType) ?? undefined
			});
		} catch {
			recError = true;
		}
	}

	function handleMood(infer: InferResult): void {
		inference.set(infer);
		mood = infer;
		refreshRecommendation();
	}

	onMount(() => {
		if (!get(consentGiven)) {
			goto('/');
			return;
		}
		mood = get(inference); // survives refresh via sessionStorage
		loadCatalog();
		refreshRecommendation();
	});
</script>

<div class="flex min-h-dvh flex-col px-4 pb-28">
	<CatalogHeader
		onPersonalize={() => (profileOpen = true)}
		onFiltersChange={refreshRecommendation}
	/>

	<main class="flex-1 pt-4">
		{#if catalogError}
			<div class="flex flex-col items-center gap-3 py-16 text-center">
				<p class="text-sm text-muted-foreground">We couldn't load the menu.</p>
				<Button onclick={loadCatalog}>Retry</Button>
			</div>
		{:else}
			{#if recError}
				<div
					class="mb-3 flex items-center justify-between rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive"
				>
					<span>Couldn't rank dishes for your mood.</span>
					<Button size="sm" variant="ghost" onclick={refreshRecommendation}>Retry</Button>
				</div>
			{/if}
			{#if mood}
				<!-- Show the work: detected mood + the nutrient targets driving the ranking,
				     inline on the main screen (stacked on phones, side column on desktop). -->
				<div class="space-y-4 md:grid md:grid-cols-[20rem_1fr] md:items-start md:gap-6 md:space-y-0">
					<TransparencyPanel
						zone={mood.zone}
						probs={mood.emotion_probs}
						nnv={recommendation?.nnv ?? undefined}
					/>
					<CatalogGrid {entries} onOpen={(e) => (selected = e)} />
				</div>
			{:else}
				<CatalogGrid {entries} onOpen={(e) => (selected = e)} />
			{/if}
		{/if}
	</main>

	<VoiceDock hasMood={mood !== null} onMood={handleMood} />

	<ProfileSheet bind:open={profileOpen} onSaved={refreshRecommendation} />
	<DishSheet entry={selected} onClose={() => (selected = null)} />
</div>
