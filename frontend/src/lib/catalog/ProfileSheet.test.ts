import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { get } from 'svelte/store';
import ProfileSheet from './ProfileSheet.svelte';
import { profile } from '$lib/stores/session';

beforeEach(() => {
	sessionStorage.clear();
	profile.set(null);
});

describe('ProfileSheet', () => {
	it('Save stores a typed profile and fires onSaved', async () => {
		const onSaved = vi.fn();
		const user = userEvent.setup({ pointerEventsCheck: 0 });
		render(ProfileSheet, { props: { open: true, onSaved } });

		await user.type(screen.getByLabelText(/age/i), '30');
		await user.type(screen.getByLabelText(/height/i), '180');
		await user.type(screen.getByLabelText(/weight/i), '75');
		await user.click(screen.getByRole('button', { name: /save/i }));

		expect(onSaved).toHaveBeenCalledTimes(1);
		expect(get(profile)).toEqual({
			age: 30,
			sex: 'male',
			height_cm: 180,
			weight_kg: 75,
			activity: 'moderate'
		});
	});

	it('Clear nulls the profile and fires onSaved', async () => {
		profile.set({ age: 40, sex: 'female', height_cm: 165, weight_kg: 60, activity: 'light' });
		const onSaved = vi.fn();
		const user = userEvent.setup({ pointerEventsCheck: 0 });
		render(ProfileSheet, { props: { open: true, onSaved } });

		await user.click(screen.getByRole('button', { name: /clear/i }));
		expect(get(profile)).toBeNull();
		expect(onSaved).toHaveBeenCalledTimes(1);
	});

	it('pre-fills the form from an existing profile', () => {
		profile.set({ age: 40, sex: 'female', height_cm: 165, weight_kg: 60, activity: 'light' });
		render(ProfileSheet, { props: { open: true, onSaved: vi.fn() } });
		expect(screen.getByLabelText(/age/i)).toHaveValue(40);
		expect(screen.getByLabelText(/height/i)).toHaveValue(165);
	});
});
