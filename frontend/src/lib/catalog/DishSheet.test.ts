import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import DishSheet from './DishSheet.svelte';
import type { CatalogEntry } from './ordering';

vi.mock('$lib/api', async (orig) => ({
	...((await orig()) as object),
	fetchImages: vi.fn(async () => ['img-a.jpg']),
	fetchRestaurants: vi.fn(async () => ({ places: [], disabled: true }))
}));

const matched: CatalogEntry = {
	food: { id: 'salmon', name: 'Grilled Salmon', source: 'usda', calories: 400, image_hint: 'salmon fillet' },
	meal: {
		food: { id: 'salmon', name: 'Grilled Salmon', source: 'usda', calories: 400, image_hint: 'salmon fillet' },
		enms: 0.82,
		m_macro: 0.9,
		m_micro: 0.7,
		satisfied_targets: ['omega3_g']
	}
};

describe('DishSheet', () => {
	it('shows the dish, loads images, and shows the match breakdown when ranked', async () => {
		render(DishSheet, { props: { entry: matched, onClose: vi.fn() } });
		expect(screen.getByText('Grilled Salmon')).toBeInTheDocument();
		expect(screen.getByText(/82%/)).toBeInTheDocument();
		expect(screen.getByText('Omega-3')).toBeInTheDocument();
		await waitFor(() => expect(screen.getByRole('img')).toHaveAttribute('src', 'img-a.jpg'));
	});

	it('hides the match section for unranked dishes', () => {
		render(DishSheet, { props: { entry: { ...matched, meal: null }, onClose: vi.fn() } });
		expect(screen.queryByText(/match/i)).toBeNull();
	});

	it('requests geolocation only after "Find nearby" is tapped', async () => {
		const getCurrentPosition = vi.fn();
		Object.defineProperty(navigator, 'geolocation', {
			configurable: true,
			value: { getCurrentPosition }
		});
		const user = userEvent.setup({ pointerEventsCheck: 0 });
		render(DishSheet, { props: { entry: matched, onClose: vi.fn() } });
		expect(getCurrentPosition).not.toHaveBeenCalled();
		await user.click(screen.getByRole('button', { name: /find nearby/i }));
		expect(getCurrentPosition).toHaveBeenCalled();
		// @ts-expect-error cleanup stub
		delete navigator.geolocation;
	});
});
