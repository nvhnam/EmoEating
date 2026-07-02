import { redirect } from '@sveltejs/kit';

// The funnel is now a single surface at /app; this route only redirects old links.
export const load = () => {
	throw redirect(307, '/app');
};
