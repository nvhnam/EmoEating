<script lang="ts">
  import { Progress } from '$lib/components/ui/progress';
  import type { EmotionProbs } from '$lib/api';

  let { probs }: { probs: EmotionProbs } = $props();

  const rows = $derived(
    Object.entries(probs).sort((a, b) => b[1] - a[1])
  );
</script>

<div class="space-y-2">
  {#each rows as [label, value] (label)}
    <div class="grid grid-cols-[6rem_1fr_3rem] items-center gap-3 text-sm">
      <span id="emotion-{label}" data-testid="emotion-label" class="capitalize text-muted-foreground"
        >{label}</span
      >
      <Progress value={value * 100} max={100} aria-labelledby="emotion-{label}" />
      <span class="text-right tabular-nums">{Math.round(value * 100)}%</span>
    </div>
  {/each}
</div>
