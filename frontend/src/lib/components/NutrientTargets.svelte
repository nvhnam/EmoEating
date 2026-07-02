<script lang="ts">
  import { ZONE_DISPLAY, nutrientLabel } from '$lib/zones';
  import type { NNVData } from '$lib/api';

  let { zone, nnv }: { zone: string; nnv?: NNVData } = $props();

  const display = $derived(ZONE_DISPLAY[zone] ?? { label: zone, blurb: '', priority: [] });
  const fmt = (n: number) => (Math.round(n * 10) / 10).toString();
  // Unit derived from the canonical key suffix (e.g. vit_c_mg → "mg", vit_d_ug → "µg").
  const unit = (key: string) =>
    key.endsWith('_mg') ? 'mg' : key.endsWith('_ug') ? 'µg' : key.endsWith('_g') ? 'g' : '';
</script>

<div class="space-y-3">
  {#if nnv}
    <div>
      <h4 class="text-sm font-medium">Per-meal macro targets</h4>
      <ul class="mt-1 space-y-0.5 text-sm text-muted-foreground">
        {#each Object.entries(nnv.macro_targets) as [key, grams] (key)}
          <li class="flex justify-between"><span>{nutrientLabel(key)}</span><span>{fmt(grams)} g</span></li>
        {/each}
      </ul>
    </div>
    <div>
      <h4 class="text-sm font-medium">Priority micronutrients</h4>
      <ul class="mt-1 space-y-0.5 text-sm text-muted-foreground">
        {#each nnv.priority_micros as key (key)}
          <li class="flex justify-between">
            <span>{nutrientLabel(key)}</span><span>{fmt(nnv.micro_targets[key] ?? 0)} {unit(key)}</span>
          </li>
        {/each}
      </ul>
    </div>
  {:else}
    <h4 class="text-sm font-medium">This mood's priority nutrients</h4>
    <div class="flex flex-wrap gap-2">
      {#each display.priority as name (name)}
        <span class="rounded-full bg-secondary px-3 py-1 text-xs">{name}</span>
      {/each}
    </div>
  {/if}
</div>
