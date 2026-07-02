<script lang="ts">
	import { flip } from 'svelte/animate';
	import DishCard from './DishCard.svelte';
	import type { CatalogEntry } from './ordering';

	let {
		entries,
		onOpen
	}: {
		entries: CatalogEntry[];
		onOpen: (entry: CatalogEntry) => void;
	} = $props();
</script>

<div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
	{#each entries as entry (entry.food.id)}
		<div animate:flip={{ duration: 250 }}>
			<DishCard food={entry.food} meal={entry.meal} onOpen={() => onOpen(entry)} />
		</div>
	{/each}
</div>
