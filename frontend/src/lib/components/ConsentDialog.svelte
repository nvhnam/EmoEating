<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog';
	import { Button } from '$lib/components/ui/button';

	let {
		open = $bindable(false),
		onAccept,
		onDecline
	}: { open?: boolean; onAccept: () => void; onDecline?: () => void } = $props();

	function accept() {
		open = false;
		onAccept();
	}
	function decline() {
		open = false;
		onDecline?.();
	}
</script>

<Dialog.Root bind:open>
	<Dialog.Content class="max-w-md">
		<Dialog.Header>
			<Dialog.Title>Before we listen</Dialog.Title>
			<Dialog.Description>
				EmoEating analyses a short voice clip to estimate how you're feeling and suggest food.
			</Dialog.Description>
		</Dialog.Header>
		<ul class="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
			<li>Your audio is processed ephemerally and is never logged or stored.</li>
			<li>No account, no emotion history — nothing leaves this session.</li>
			<li>This is a wellness aid, not medical or clinical advice.</li>
		</ul>
		<Dialog.Footer class="gap-2">
			<Button variant="ghost" onclick={decline}>Not now</Button>
			<Button onclick={accept}>Accept &amp; continue</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
