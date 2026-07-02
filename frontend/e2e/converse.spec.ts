// frontend/e2e/converse.spec.ts
import { expect, test } from '@playwright/test';

test('single-surface funnel: consent → /app → talk → results render in place', async ({ page }) => {
  // ---- HTTP route stubs (Playwright network layer) ----
  await page.route('**/api/foods', (route) =>
    route.fulfill({
      json: {
        foods: [
          { id: 'salad', name: 'Rainbow Salad', source: 'usda', calories: 220, image_hint: 'salad' },
          { id: 'candy', name: 'Gummy Candy', source: 'off', calories: 350, image_hint: null }
        ]
      }
    })
  );
  await page.route('**/api/realtime/token', (route) =>
    route.fulfill({
      json: { provider: 'openai', client_secret: 'test-ephemeral-secret', model: 'gpt-4o-realtime-preview', voice: 'alloy' }
    })
  );
  await page.route('**/api/recommend', (route) =>
    route.fulfill({
      json: {
        meals: [
          {
            food: { id: 'salad', name: 'Rainbow Salad', source: 'usda', calories: 220, image_hint: 'salad' },
            enms: 0.78,
            m_macro: 0.82,
            m_micro: 0.65,
            satisfied_targets: ['vit_c_mg', 'fiber_g']
          }
        ],
        nnv: {
          zone: 'POS_ACTIVE',
          macro_targets: { protein_g: 37, carb_g: 75, fat_g: 16 },
          micro_targets: { vit_c_mg: 30, vit_e_mg: 5 },
          priority_micros: ['vit_c_mg', 'vit_e_mg']
        }
      }
    })
  );
  await page.route('**/api/images**', (route) => route.fulfill({ json: { images: [] } }));
  await page.route('**/api/restaurants**', (route) =>
    route.fulfill({ json: { places: [], disabled: true } })
  );

  // ---- Browser-side stubs injected BEFORE page JS runs ----
  await page.addInitScript(() => {
    // Stub RTCPeerConnection
    class FakePc {
      ontrack: ((e: { streams: MediaStream[] }) => void) | null = null;
      _dc = {
        readyState: 'open',
        onmessage: null as ((e: { data: string }) => void) | null,
        send(_: string) {
          // Simulate the agent responding (speak → stop) so greeting + wrap-up complete.
          setTimeout(
            () => this.onmessage?.({ data: JSON.stringify({ type: 'output_audio_buffer.started' }) }),
            50
          );
          setTimeout(
            () => this.onmessage?.({ data: JSON.stringify({ type: 'output_audio_buffer.stopped' }) }),
            250
          );
        },
        close() {}
      };
      addTrack() {}
      createDataChannel() { return this._dc; }
      async createOffer() { return { sdp: 'v=0\r\n', type: 'offer' }; }
      async setLocalDescription() {}
      async setRemoteDescription() {}
      close() {}
    }
    (window as any).RTCPeerConnection = FakePc;

    // Stub getUserMedia — returns a silent fake stream
    const fakeTrack = { stop() {}, kind: 'audio', enabled: true };
    const fakeStream = {
      getAudioTracks: () => [fakeTrack],
      getTracks: () => [fakeTrack]
    };
    Object.defineProperty(navigator, 'mediaDevices', {
      value: { getUserMedia: async () => fakeStream },
      writable: true
    });

    // Stub AudioContext so the worklet module load doesn't fail
    (window as any).AudioContext = class {
      sampleRate = 48000;
      destination = {};
      audioWorklet = { addModule: async () => {} };
      createMediaStreamSource() { return { connect() {}, disconnect() {} }; }
      close() {}
    };
    (window as any).AudioWorkletNode = class {
      port = { onmessage: null };
      connect() {}
      disconnect() {}
    };

    // Stub WebSocket: if URL contains /ws/emotion, auto-fire a 'done' event after 400 ms
    (window as any).WebSocket = class {
      static OPEN = 1;
      static CONNECTING = 0;
      readyState = 1;
      binaryType = 'arraybuffer';
      onmessage: ((e: { data: string }) => void) | null = null;
      onopen: (() => void) | null = null;
      constructor(public url: string) {
        if (url.includes('/ws/emotion')) {
          setTimeout(() => {
            this.onmessage?.({
              data: JSON.stringify({
                type: 'done',
                infer: {
                  emotion_probs: { happy: 0.75, neutral: 0.25 },
                  valence: 0.78,
                  arousal: 0.48,
                  zone: 'POS_ACTIVE'
                }
              })
            });
          }, 400);
        }
      }
      send() {}
      close() { this.readyState = 3; }
    };

    // Patch fetch so OpenAI SDP calls return a fake SDP answer without real network
    const _origFetch = window.fetch.bind(window);
    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).includes('openai.com')) {
        return new Response('v=0\r\nfake-sdp-answer', { status: 200, headers: { 'content-type': 'application/sdp' } });
      }
      return _origFetch(input, init);
    };
  });

  // ---- Drive the funnel (single surface: the URL stays on /app throughout) ----

  // 1. Home → single consent: check the box (enables Get started) → /app
  await page.goto('/');
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: /get started/i }).click();
  await expect(page).toHaveURL(/\/app/);

  // 2. The catalog renders immediately — this IS the app screen.
  await expect(page.getByText('Rainbow Salad')).toBeVisible();
  await expect(page.getByText('Gummy Candy')).toBeVisible();

  // 3. Talk via the bottom dock.
  await page.getByRole('button', { name: /find what fits you/i }).click();

  // 4. The stub WS fires 'done'; the grid re-ranks in place, and the detected mood
  //    + nutrient targets are shown inline on the main screen.
  await expect(page.getByText(/fits your mood/i)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText('Positive · Active').first()).toBeVisible();
  await expect(page.getByText(/detected zone/i)).toBeVisible();
  await expect(page.getByText(/per-meal macro targets/i)).toBeVisible();
  await expect(page).toHaveURL(/\/app/);
});
