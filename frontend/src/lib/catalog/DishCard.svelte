<script lang="ts">
	import { Badge } from '$lib/components/ui/badge';
	import type { FoodOut, MealOut } from '$lib/api';

	let {
		food,
		meal = null,
		onOpen
	}: {
		food: FoodOut;
		meal?: MealOut | null;
		onOpen: () => void;
	} = $props();

	const pct = (n: number) => `${Math.round(n * 100)}%`;
</script>

<button
	type="button"
	class="flex h-full w-full flex-col items-start gap-1.5 rounded-xl border bg-card p-3 text-left shadow-sm transition-shadow hover:shadow-md"
	onclick={onOpen}
>
	{#if meal}
		<Badge class="text-[10px]">Fits your mood · {pct(meal.enms)}</Badge>
	{/if}
	<span class="text-sm font-medium leading-snug">{food.name}</span>
	<span class="text-xs text-muted-foreground">
		{food.source}{#if food.calories != null}&nbsp;· {Math.round(food.calories)} kcal{/if}
	</span>
</button>
