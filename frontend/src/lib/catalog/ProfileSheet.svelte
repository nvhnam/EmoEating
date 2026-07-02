<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import { get } from 'svelte/store';
	import { profile } from '$lib/stores/session';

	let { open = $bindable(false), onSaved }: { open?: boolean; onSaved: () => void } = $props();

	let age = $state('');
	let sex = $state<'male' | 'female'>('male');
	let heightCm = $state('');
	let weightKg = $state('');
	let activity = $state('moderate');

	// Re-seed the form from the store on every open so edits start from what's saved.
	$effect(() => {
		if (!open) return;
		const p = get(profile);
		age = p ? String(p.age) : '';
		sex = p?.sex ?? 'male';
		heightCm = p ? String(p.height_cm) : '';
		weightKg = p ? String(p.weight_kg) : '';
		activity = p?.activity ?? 'moderate';
	});

	function save() {
		profile.set({
			age: Number(age),
			sex,
			height_cm: Number(heightCm),
			weight_kg: Number(weightKg),
			activity
		});
		open = false;
		onSaved();
	}

	function clear() {
		profile.set(null);
		open = false;
		onSaved();
	}
</script>

<Dialog.Root bind:open>
	<Dialog.Content class="max-w-md">
		<Dialog.Header>
			<Dialog.Title>Tailor portions to you</Dialog.Title>
			<Dialog.Description>
				Used only to scale calorie targets (Mifflin–St Jeor). Clear it any time for ratio-only
				targets.
			</Dialog.Description>
		</Dialog.Header>

		<div class="grid grid-cols-2 gap-4">
			<div class="space-y-1">
				<Label for="ps-age">Age</Label>
				<Input id="ps-age" type="number" inputmode="numeric" bind:value={age} />
			</div>
			<div class="space-y-1">
				<Label for="ps-sex">Sex</Label>
				<select id="ps-sex" class="h-10 w-full rounded-md border bg-background px-3" bind:value={sex}>
					<option value="male">Male</option>
					<option value="female">Female</option>
				</select>
			</div>
			<div class="space-y-1">
				<Label for="ps-height">Height (cm)</Label>
				<Input id="ps-height" type="number" inputmode="numeric" bind:value={heightCm} />
			</div>
			<div class="space-y-1">
				<Label for="ps-weight">Weight (kg)</Label>
				<Input id="ps-weight" type="number" inputmode="numeric" bind:value={weightKg} />
			</div>
			<div class="col-span-2 space-y-1">
				<Label for="ps-activity">Activity level</Label>
				<select
					id="ps-activity"
					class="h-10 w-full rounded-md border bg-background px-3"
					bind:value={activity}
				>
					<option value="sedentary">Sedentary</option>
					<option value="light">Light</option>
					<option value="moderate">Moderate</option>
					<option value="active">Active</option>
					<option value="very_active">Very active</option>
				</select>
			</div>
		</div>

		<Dialog.Footer class="gap-2">
			<Button variant="ghost" onclick={clear}>Clear</Button>
			<Button onclick={save}>Save</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
