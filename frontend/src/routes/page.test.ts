import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/svelte';
import Page from './+page.svelte';
import type { VoiceConfig } from '$lib/api';

vi.mock('$app/navigation', () => ({ goto: vi.fn() }));

// The spy only records that the home page called fetchVoiceConfig; the actual
// promise comes from `voiceConfigImpl`. Routing the rejection through a plain
// wrapper (not the spy's return value) avoids a Vitest 4 quirk where a spy that
// *returns* a rejected promise re-surfaces that rejection across test boundaries
// even though the component's try/catch already handles it.
const fetchVoiceConfig = vi.fn();
let voiceConfigImpl: () => Promise<VoiceConfig>;
vi.mock('$lib/api', async (orig) => ({
	...((await orig()) as object),
	fetchVoiceConfig: () => {
		fetchVoiceConfig();
		return voiceConfigImpl();
	}
}));

beforeEach(() => {
	fetchVoiceConfig.mockReset();
	voiceConfigImpl = () => Promise.resolve({ provider: 'openai', provider_name: 'OpenAI' });
});

describe('home consent', () => {
	it('names the active provider from /api/voice/config', async () => {
		voiceConfigImpl = () => Promise.resolve({ provider: 'gemini', provider_name: 'Google Gemini' });
		render(Page);
		await waitFor(() => expect(screen.getByText(/Google Gemini/)).toBeInTheDocument());
	});

	it('falls back to a neutral label when the config fetch fails', async () => {
		voiceConfigImpl = () => Promise.reject(new Error('down'));
		render(Page);
		// The fallback text equals the default, so wait for onMount to actually attempt
		// the fetch (and handle the rejection) before asserting the neutral label survives.
		await waitFor(() => expect(fetchVoiceConfig).toHaveBeenCalled());
		expect(screen.getByText(/our voice AI provider/i)).toBeInTheDocument();
	});
});
