import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import ConsentDialog from './ConsentDialog.svelte';

describe('ConsentDialog', () => {
	it('states the privacy terms and fires onAccept', async () => {
		const onAccept = vi.fn();
		render(ConsentDialog, { props: { open: true, onAccept } });
		expect(screen.getByText(/never logged|not stored|ephemeral/i)).toBeInTheDocument();
		await userEvent.click(screen.getByRole('button', { name: /accept & continue/i }));
		expect(onAccept).toHaveBeenCalledOnce();
	});

	it('fires onDecline from "Not now"', async () => {
		const onDecline = vi.fn();
		render(ConsentDialog, { props: { open: true, onAccept: vi.fn(), onDecline } });
		await userEvent.click(screen.getByRole('button', { name: /not now/i }));
		expect(onDecline).toHaveBeenCalledOnce();
	});
});
