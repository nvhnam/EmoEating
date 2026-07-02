import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { get } from 'svelte/store';
import CatalogHeader from './CatalogHeader.svelte';
import { mealType } from '$lib/stores/session';

beforeEach(() => {
	sessionStorage.clear();
	mealType.set(null);
});

const props = () => ({
	onPersonalize: vi.fn(),
	onFiltersChange: vi.fn()
});

describe('CatalogHeader', () => {
	it('shows no mood badge — the transparency panel owns mood display', () => {
		render(CatalogHeader, { props: props() });
		expect(screen.queryByText(/calm|positive|negative/i)).toBeNull();
	});

	it('changing the meal chip writes the store and fires onFiltersChange', async () => {
		const p = props();
		const user = userEvent.setup({ pointerEventsCheck: 0 });
		render(CatalogHeader, { props: p });
		await user.selectOptions(screen.getByLabelText(/meal/i), 'dinner');
		expect(get(mealType)).toBe('dinner');
		expect(p.onFiltersChange).toHaveBeenCalled();
	});

	it('Personalize chip fires onPersonalize', async () => {
		const p = props();
		const user = userEvent.setup({ pointerEventsCheck: 0 });
		render(CatalogHeader, { props: p });
		await user.click(screen.getByRole('button', { name: /personalize/i }));
		expect(p.onPersonalize).toHaveBeenCalled();
	});
});
