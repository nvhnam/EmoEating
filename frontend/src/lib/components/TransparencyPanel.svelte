<script lang="ts">
  import EmotionBars from './EmotionBars.svelte';
  import NutrientTargets from './NutrientTargets.svelte';
  import { ZONE_DISPLAY } from '$lib/zones';
  import type { EmotionProbs, NNVData } from '$lib/api';

  let { zone, probs, nnv }: { zone: string; probs: EmotionProbs; nnv?: NNVData } = $props();

  const display = $derived(ZONE_DISPLAY[zone] ?? { label: zone, blurb: '', priority: [] });
</script>

<aside class="space-y-5 rounded-xl border bg-card p-5">
  <header>
    <p class="text-xs uppercase tracking-wide text-muted-foreground">Detected zone</p>
    <h3 class="text-lg font-semibold">{display.label}</h3>
    <p class="text-sm text-muted-foreground">{display.blurb}</p>
  </header>
  <div>
    <p class="mb-2 text-xs uppercase tracking-wide text-muted-foreground">Emotion probabilities</p>
    <EmotionBars {probs} />
  </div>
  <NutrientTargets {zone} {nnv} />
</aside>
