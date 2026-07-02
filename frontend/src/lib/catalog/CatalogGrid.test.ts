import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import CatalogGrid from './CatalogGrid.svelte';
import type { CatalogEntry } from './ordering';

const entry = (id: string, enms: number | null): CatalogEntry => ({
	food: { id, name: `Dish ${id}`, source: 'usda', calories: 320, image_hint: null },
	meal:
		enms === null
			? null
			: {
					food: { id, name: `Dish ${id}`, source: 'usda', calories: 320, image_hint: null },
					enms,
					m_macro: 0.8,
					m_micro: 0.6,
					satisfied_targets: ['protein_g']
				}
});

describe('CatalogGrid', () => {
	it('renders every entry; only matched dishes get the mood badge with ENMS %', () => {
		render(CatalogGrid, { props: { entries: [entry('a', 0.82), entry('b', null)], onOpen: vi.fn() } });
		expect(screen.getByText('Dish a')).toBeInTheDocument();
		expect(screen.getByText('Dish b')).toBeInTheDocument();
		expect(screen.getAllByText(/fits your mood/i)).toHaveLength(1);
		expect(screen.getByText(/82%/)).toBeInTheDocument();
	});

	it('clicking a card fires onOpen with its entry', async () => {
		const onOpen = vi.fn();
		const user = userEvent.setup({ pointerEventsCheck: 0 });
		render(CatalogGrid, { props: { entries: [entry('a', null)], onOpen } });
		await user.click(screen.getByRole('button', { name: /dish a/i }));
		expect(onOpen).toHaveBeenCalledWith(
			expect.objectContaining({ food: expect.objectContaining({ id: 'a' }) })
		);
	});
});
