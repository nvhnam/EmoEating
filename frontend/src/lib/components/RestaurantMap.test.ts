import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/svelte';
import RestaurantMap from './RestaurantMap.svelte';
import * as api from '$lib/api';

// maplibre is touched when places exist; stub to avoid WebGL in jsdom.
// Use real functions (not arrows) so they are constructable via `new`.
vi.mock('maplibre-gl', () => ({
	default: {
		Map: vi.fn(function () {
			return { on: vi.fn(), remove: vi.fn(), addControl: vi.fn() };
		}),
		Marker: vi.fn(function () {
			return { setLngLat: () => ({ addTo: vi.fn() }) };
		})
	}
}));

beforeEach(() => vi.restoreAllMocks());

describe('RestaurantMap', () => {
	it('prompts to enable location when coords are null', () => {
		render(RestaurantMap, { props: { food: 'pho', coords: null } });
		expect(screen.getByText(/enable location/i)).toBeInTheDocument();
	});

	it('lists nearby places nearest-first', async () => {
		vi.spyOn(api, 'fetchRestaurants').mockResolvedValue({
			places: [
				{ name: 'Corner Pho', lat: 10.77, lng: 106.69, distance_m: 120, address: '1 Near St' },
				{ name: 'Far Pho', lat: 10.8, lng: 106.7, distance_m: 1500, address: '9 Far Rd' }
			]
		});
		render(RestaurantMap, { props: { food: 'pho', coords: { lat: 10.77, lng: 106.69 } } });
		await waitFor(() => expect(screen.getByText('Corner Pho')).toBeInTheDocument());
		expect(screen.getByText(/120 m/)).toBeInTheDocument();
	});

	it('does not fetch while coords are null, then fetches when coords arrive', async () => {
		const spy = vi.spyOn(api, 'fetchRestaurants').mockResolvedValue({
			places: [{ name: 'Corner Pho', lat: 10.77, lng: 106.69, distance_m: 120, address: '1 Near St' }]
		});
		const { rerender } = render(RestaurantMap, { props: { food: 'pho', coords: null } });
		expect(screen.getByText(/enable location/i)).toBeInTheDocument();
		expect(spy).not.toHaveBeenCalled();

		await rerender({ food: 'pho', coords: { lat: 10.77, lng: 106.69 } });
		await waitFor(() => expect(screen.getByText('Corner Pho')).toBeInTheDocument());
		expect(spy).toHaveBeenCalledWith('pho', 10.77, 106.69);
	});

	it('shows a neutral banner when restaurants are disabled', async () => {
		vi.spyOn(api, 'fetchRestaurants').mockResolvedValue({ places: [], disabled: true });
		render(RestaurantMap, { props: { food: 'pho', coords: { lat: 10.77, lng: 106.69 } } });
		await waitFor(() =>
			expect(screen.getByText(/nearby restaurants are unavailable/i)).toBeInTheDocument()
		);
	});
});
