<!-- frontend/src/lib/components/RestaurantMap.svelte -->
<script lang="ts">
	import { onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import type { Map as MaplibreMap } from 'maplibre-gl';
	import { fetchRestaurants, type Place } from '$lib/api';

	let { food, coords }: { food: string; coords: { lat: number; lng: number } | null } = $props();

	let places = $state<Place[]>([]);
	let disabled = $state(false);
	let mapEl = $state<HTMLDivElement | null>(null);

	// MapLibre map instance kept so we can tear down the WebGL context on
	// remount / coords change (avoids leaking contexts).
	let map: MaplibreMap | null = null;

	const fmtDist = (m: number) => (m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(1)} km`);

	// Fetch reacts to `coords` (and `food`): geolocation resolves AFTER the
	// component mounts, so we must re-run when the prop becomes non-null.
	$effect(() => {
		// Track deps explicitly.
		const c = coords;
		const f = food;
		if (!c) {
			places = [];
			disabled = false;
			return;
		}
		let cancelled = false;
		(async () => {
			try {
				const res = await fetchRestaurants(f, c.lat, c.lng);
				if (cancelled) return; // coords changed again before this resolved
				disabled = res.disabled ?? false;
				places = res.places;
			} catch {
				if (cancelled) return;
				disabled = true; // degrade quietly; meals already shown
				places = [];
			}
		})();
		return () => {
			cancelled = true;
		};
	});

	// Map init reacts to places/coords/mapEl. Re-running tears down the prior
	// map first so we never leak a WebGL context.
	$effect(() => {
		const c = coords;
		const list = places;
		const el = mapEl;
		if (!browser || !el || list.length === 0 || !c) return;
		let cancelled = false;
		(async () => {
			const maplibre = (await import('maplibre-gl')).default;
			if (cancelled || !el) return;
			map?.remove();
			map = new maplibre.Map({
				container: el,
				style: 'https://demotiles.maplibre.org/style.json',
				center: [c.lng, c.lat],
				zoom: 13
			});
			for (const p of list) new maplibre.Marker().setLngLat([p.lng, p.lat]).addTo(map);
		})();
		return () => {
			cancelled = true;
			map?.remove();
			map = null;
		};
	});

	onDestroy(() => {
		map?.remove();
		map = null;
	});
</script>

<section class="space-y-3">
	<h3 class="text-lg font-semibold">Nearby places to eat</h3>

	{#if !coords}
		<p class="text-sm text-muted-foreground">Enable location to see restaurants near you.</p>
	{:else if disabled}
		<p class="text-sm text-muted-foreground">Nearby restaurants are unavailable right now.</p>
	{:else}
		{#if places.length > 0}
			<div
				bind:this={mapEl}
				class="h-64 w-full overflow-hidden rounded-lg border"
				data-testid="map"
			></div>
		{/if}
		<ul class="divide-y rounded-lg border">
			{#each places as p (p.name + p.distance_m)}
				<li class="flex items-center justify-between px-4 py-2 text-sm">
					<span>
						<span class="font-medium">{p.name}</span>
						<span class="block text-xs text-muted-foreground">{p.address}</span>
					</span>
					<span class="tabular-nums text-muted-foreground">{fmtDist(p.distance_m)}</span>
				</li>
			{/each}
		</ul>
	{/if}
</section>
