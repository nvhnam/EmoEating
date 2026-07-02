<script lang="ts">
  import * as Dialog from '$lib/components/ui/dialog';
  import { Button } from '$lib/components/ui/button';
  import { voiceConsentGiven } from '$lib/stores/session';

  let {
    open = $bindable(false),
    onAccept,
    onDecline
  }: { open?: boolean; onAccept: () => void; onDecline?: () => void } = $props();

  let screened = $state(false);

  // Reset the screening checkbox whenever the dialog is (re-)opened so a prior
  // acceptance from a previous session doesn't pre-enable the Accept button.
  $effect(() => {
    if (open) screened = false;
  });

  function accept() {
    open = false;
    voiceConsentGiven.set(true);
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
      <Dialog.Title>Before we start the conversation</Dialog.Title>
      <Dialog.Description>
        Please read carefully — this feature uses a third-party service.
      </Dialog.Description>
    </Dialog.Header>

    <div class="space-y-4 text-sm">
      <section class="rounded-md border bg-muted/40 p-3 space-y-1">
        <p class="font-medium">How your audio is used</p>
        <p class="text-muted-foreground">
          Your voice is streamed to OpenAI to power the conversation and is
          processed under OpenAI's data policy, which may include
          <strong>short-term retention for safety monitoring</strong>.
          We do not store your audio, transcript, or emotion data — the
          emotion read runs on our server in memory and is discarded after your session.
        </p>
      </section>

      <section>
        <label class="flex items-start gap-3 cursor-pointer">
          <input type="checkbox" class="mt-0.5 shrink-0" bind:checked={screened} />
          <span class="text-muted-foreground">
            I understand this feature is designed for general wellbeing and is
            <strong>not a clinical tool</strong>. I will not use it as a substitute for
            medical or mental health care, and I am not in acute distress.
          </span>
        </label>
      </section>
    </div>

    <Dialog.Footer class="gap-2">
      <Button variant="ghost" onclick={decline}>Not now</Button>
      <Button onclick={accept} disabled={!screened}>Accept &amp; continue</Button>
    </Dialog.Footer>
  </Dialog.Content>
</Dialog.Root>
