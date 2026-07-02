<script lang="ts">
	import { mealType } from '$lib/stores/session';

	let {
		onPersonalize,
		onFiltersChange
	}: {
		onPersonalize: () => void;
		onFiltersChange: () => void;
	} = $props();
</script>

<header class="sticky top-0 z-30 -mx-4 border-b bg-background/95 px-4 pb-3 pt-4 backdrop-blur">
	<div class="flex items-center justify-between">
		<div class="flex items-center gap-2 font-semibold">
			<span aria-hidden="true">🍃</span>
			<span>EmoEating</span>
		</div>
		<button
			type="button"
			class="rounded-full border px-3 py-1 text-sm"
			onclick={onPersonalize}
		>
			Personalize
		</button>
	</div>

	<div class="mt-3 flex gap-2 overflow-x-auto">
		<label class="flex shrink-0 items-center rounded-full border px-3 py-1 text-sm">
			<span class="sr-only">Meal</span>
			<select
				class="bg-transparent"
				bind:value={$mealType}
				onchange={onFiltersChange}
				aria-label="Meal"
			>
				<option value={null}>Any meal</option>
				<option value="breakfast">Breakfast</option>
				<option value="lunch">Lunch</option>
				<option value="dinner">Dinner</option>
				<option value="snack">Snack</option>
			</select>
		</label>
	</div>
</header>
