import { writable, type Writable } from 'svelte/store';
import type { InferResult, Profile } from '$lib/api';

// Session-scoped persistence: state survives a refresh within the tab/session
// (sessionStorage, not localStorage), so the single-surface flow isn't lost on
// reload. Cleared when the tab closes or on resetSession().
function persisted<T>(key: string, initial: T): Writable<T> {
	let start = initial;
	if (typeof sessionStorage !== 'undefined') {
		const raw = sessionStorage.getItem(key);
		if (raw !== null) {
			try {
				start = JSON.parse(raw) as T;
			} catch {
				/* corrupt value — fall back to initial */
			}
		}
	}
	const store = writable<T>(start);
	if (typeof sessionStorage !== 'undefined') {
		store.subscribe((v) => {
			try {
				sessionStorage.setItem(key, JSON.stringify(v));
			} catch {
				/* storage full / unavailable — non-fatal */
			}
		});
	}
	return store;
}

export const consentGiven = persisted<boolean>('ee:consent', false);
export const voiceConsentGiven = persisted<boolean>('ee:voiceConsent', false);
export const profile = persisted<Profile | null>('ee:profile', null);
// Which meal we're recommending for; scales portion targets. null -> flat 1/3.
export const mealType = persisted<string | null>('ee:mealType', null);
export const inference = persisted<InferResult | null>('ee:inference', null);

export function resetSession(): void {
	consentGiven.set(false);
	voiceConsentGiven.set(false);
	profile.set(null);
	mealType.set(null);
	inference.set(null);
}
