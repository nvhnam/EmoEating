<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog';
	import { Badge } from '$lib/components/ui/badge';
	import { Button } from '$lib/components/ui/button';
	import RestaurantMap from '$lib/components/RestaurantMap.svelte';
	import { fetchImages } from '$lib/api';
	import { nutrientLabel } from '$lib/zones';
	import type { CatalogEntry } from './ordering';

	let { entry = null, onClose }: { entry?: CatalogEntry | null; onClose: () => void } = $props();

	let images = $state<string[]>([]);
	let coords = $state<{ lat: number; lng: number } | null>(null);
	let showMap = $state(false);
	const open = $derived(entry !== null);
	const pct = (n: number) => `${Math.round(n * 100)}%`;

	// Reset per dish; images load lazily on open (detail-only, per spec).
	$effect(() => {
		images = [];
		showMap = false;
		coords = null;
		const e = entry;
		if (!e) return;
		fetchImages(e.food.image_hint ?? e.food.name)
			.then((i) => (images = i))
			.catch(() => (images = []));
	});

	// Geolocation is on-demand only — never on page load.
	function findNearby() {
		showMap = true;
		if (typeof navigator !== 'undefined' && navigator.geolocation) {
			navigator.geolocation.getCurrentPosition(
				(pos) => (coords = { lat: pos.coords.latitude, lng: pos.coords.longitude }),
				() => (coords = null)
			);
		}
	}
</script>

<Dialog.Root {open} onOpenChange={(o) => !o && onClose()}>
	<Dialog.Content class="max-h-[85vh] max-w-md overflow-y-auto">
		{#if entry}
			<Dialog.Header>
				<Dialog.Title>{entry.food.name}</Dialog.Title>
				<Dialog.Description>
					{entry.food.source}{#if entry.food.calories != null}&nbsp;· {Math.round(
							entry.food.calories
						)} kcal{/if}
				</Dialog.Description>
			</Dialog.Header>

			{#if images.length > 0}
				<div class="grid grid-cols-3 gap-2">
					{#each images.slice(0, 3) as src (src)}
						<img {src} alt={entry.food.name} class="h-24 w-full rounded-md object-cover" loading="lazy" />
					{/each}
				</div>
			{/if}

			{#if entry.meal}
				<div class="space-y-2 rounded-md border bg-muted/40 p-3">
					<div class="flex items-center justify-between text-sm">
						<span class="text-muted-foreground">Match (ENMS)</span>
						<span class="font-semibold tabular-nums">{pct(entry.meal.enms)}</span>
					</div>
					<div class="flex gap-4 text-xs text-muted-foreground">
						<span>Macro {pct(entry.meal.m_macro)}</span>
						<span>Micro {pct(entry.meal.m_micro)}</span>
					</div>
					{#if entry.meal.satisfied_targets.length > 0}
						<div class="flex flex-wrap gap-1.5">
							{#each entry.meal.satisfied_targets as key (key)}
								<Badge variant="secondary">{nutrientLabel(key)}</Badge>
							{/each}
						</div>
					{/if}
				</div>
			{/if}

			{#if showMap}
				<RestaurantMap food={entry.food.image_hint ?? entry.food.name} {coords} />
			{:else}
				<Button variant="outline" onclick={findNearby}>Find nearby</Button>
			{/if}
		{/if}
	</Dialog.Content>
</Dialog.Root>
