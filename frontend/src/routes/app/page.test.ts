import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import Page from './+page.svelte';
import { consentGiven, inference, mealType, profile } from '$lib/stores/session';

const goto = vi.fn();
vi.mock('$app/navigation', () => ({ goto: (...a: unknown[]) => goto(...a) }));

const fetchFoods = vi.fn();
const recommend = vi.fn();
vi.mock('$lib/api', async (orig) => ({
	...((await orig()) as object),
	fetchFoods: (...a: unknown[]) => fetchFoods(...a),
	recommend: (...a: unknown[]) => recommend(...a),
	fetchImages: vi.fn(async () => []),
	fetchRealtimeToken: vi.fn(async () => ({
		provider: 'openai',
		client_secret: 'x',
		model: 'm',
		voice: 'v'
	}))
}));

const FOODS = [
	{ id: 'salmon', name: 'Grilled Salmon', source: 'usda', calories: 400, image_hint: null },
	{ id: 'candy', name: 'Gummy Candy', source: 'off', calories: 350, image_hint: null }
];
const REC = {
	meals: [{ food: FOODS[1], enms: 0.9, m_macro: 0.9, m_micro: 0.9, satisfied_targets: [] }],
	nnv: { zone: 'POS_ACTIVE', macro_targets: {}, macro_weights: {}, micro_targets: {}, priority_micros: [] }
};
const INFER = { emotion_probs: { happy: 1 }, valence: 0.5, arousal: 0.5, zone: 'POS_ACTIVE' };

beforeEach(() => {
	sessionStorage.clear();
	goto.mockClear();
	fetchFoods.mockReset().mockResolvedValue(FOODS);
	recommend.mockReset().mockResolvedValue(REC);
	consentGiven.set(true);
	inference.set(null);
	profile.set(null);
	mealType.set(null);
});

afterEach(() => vi.restoreAllMocks());

describe('/app catalog screen', () => {
	it('redirects to / when consent is missing', async () => {
		consentGiven.set(false);
		render(Page);
		await waitFor(() => expect(goto).toHaveBeenCalledWith('/'));
	});

	it('loads and renders the catalog; no recommend call without a mood', async () => {
		render(Page);
		expect(await screen.findByText('Grilled Salmon')).toBeInTheDocument();
		expect(screen.getByText('Gummy Candy')).toBeInTheDocument();
		expect(recommend).not.toHaveBeenCalled();
		expect(screen.queryByText(/fits your mood/i)).toBeNull();
	});

	it('with a persisted mood, re-fetches the ranking on load and badges matches', async () => {
		inference.set(INFER);
		render(Page);
		expect(await screen.findByText(/fits your mood/i)).toBeInTheDocument();
		expect(recommend).toHaveBeenCalledWith({
			zone: 'POS_ACTIVE',
			profile: undefined,
			meal_type: undefined
		});
		// the transparency panel is inline on the main screen: detected zone,
		// emotion probabilities, nutrient targets (no header chip — panel owns mood).
		expect(screen.getByText(/positive · active/i)).toBeInTheDocument();
		expect(screen.getByText(/detected zone/i)).toBeInTheDocument();
		expect(screen.getByText(/emotion probabilities/i)).toBeInTheDocument();
		expect(screen.getByText(/per-meal macro targets/i)).toBeInTheDocument();
	});

	it('shows no transparency panel before a mood exists', async () => {
		render(Page);
		await screen.findByText('Grilled Salmon');
		expect(screen.queryByText(/detected zone/i)).toBeNull();
	});

	it('changing the meal chip re-fetches the ranking when a mood exists', async () => {
		inference.set(INFER);
		render(Page);
		await screen.findByText(/fits your mood/i);
		const user = userEvent.setup({ pointerEventsCheck: 0 });
		await user.selectOptions(screen.getByLabelText(/meal/i), 'dinner');
		await waitFor(() =>
			expect(recommend).toHaveBeenLastCalledWith({
				zone: 'POS_ACTIVE',
				profile: undefined,
				meal_type: 'dinner'
			})
		);
	});

	it('catalog failure shows a retry state that reloads', async () => {
		fetchFoods.mockRejectedValueOnce(new Error('down'));
		render(Page);
		const retry = await screen.findByRole('button', { name: /retry/i });
		const user = userEvent.setup({ pointerEventsCheck: 0 });
		await user.click(retry);
		expect(await screen.findByText('Grilled Salmon')).toBeInTheDocument();
	});
});
