import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { recommend, fetchFoods, fetchImages, fetchRestaurants, fetchVoiceConfig, ApiError } from './api';

const BASE = 'http://localhost:8000';
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('api client', () => {
	it('POSTs JSON to /api/recommend', async () => {
		server.use(
			http.post(`${BASE}/api/recommend`, async ({ request }) => {
				const body = (await request.json()) as { zone: string };
				expect(body.zone).toBe('POS_ACTIVE');
				return HttpResponse.json({
					meals: [
						{
							food: {
								id: 'salmon',
								name: 'Salmon',
								source: 'usda',
								calories: 400,
								image_hint: 'salmon'
							},
							enms: 0.8,
							m_macro: 0.9,
							m_micro: 0.7,
							satisfied_targets: ['protein_g', 'omega3_g']
						}
					],
					nnv: {
						zone: 'POS_ACTIVE',
						macro_targets: { protein_g: 30 },
						micro_targets: { vit_c_mg: 30 },
						priority_micros: ['vit_c_mg', 'vit_e_mg']
					}
				});
			})
		);
		const out = await recommend({ zone: 'POS_ACTIVE' });
		expect(out.meals[0].food.id).toBe('salmon');
		expect(out.nnv.priority_micros).toContain('vit_c_mg');
	});

	it('GETs the food catalog and unwraps foods', async () => {
		server.use(
			http.get(`${BASE}/api/foods`, () =>
				HttpResponse.json({
					foods: [{ id: 'a', name: 'A', source: 's', calories: 100, image_hint: null }]
				})
			)
		);
		const foods = await fetchFoods();
		expect(foods).toHaveLength(1);
		expect(foods[0].id).toBe('a');
	});

	it('GETs images and unwraps the array', async () => {
		server.use(
			http.get(`${BASE}/api/images`, () => HttpResponse.json({ images: ['a.jpg', 'b.jpg'] }))
		);
		expect(await fetchImages('sushi')).toEqual(['a.jpg', 'b.jpg']);
	});

	it('GETs restaurants with lat/lng and passes through disabled', async () => {
		server.use(
			http.get(`${BASE}/api/restaurants`, () => HttpResponse.json({ places: [], disabled: true }))
		);
		const out = await fetchRestaurants('pho', 10.77, 106.69);
		expect(out.disabled).toBe(true);
		expect(out.places).toEqual([]);
	});

	it('throws ApiError on non-2xx', async () => {
		server.use(
			http.post(`${BASE}/api/recommend`, () =>
				HttpResponse.json({ detail: 'unknown zone: bogus' }, { status: 422 })
			)
		);
		await expect(recommend({ zone: 'bogus' })).rejects.toBeInstanceOf(ApiError);
	});

	it('fetchVoiceConfig GETs /api/voice/config and returns provider', async () => {
		const f = vi.fn().mockResolvedValue(
			new Response(JSON.stringify({ provider: 'gemini', provider_name: 'Google Gemini' }), {
				status: 200,
				headers: { 'content-type': 'application/json' }
			})
		);
		vi.stubGlobal('fetch', f);
		try {
			const cfg = await fetchVoiceConfig();
			expect(cfg).toEqual({ provider: 'gemini', provider_name: 'Google Gemini' });
			expect(f.mock.calls[0][0]).toContain('/api/voice/config');
		} finally {
			vi.unstubAllGlobals();
		}
	});
});
