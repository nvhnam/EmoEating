import { describe, it, expect } from 'vitest';
import { get } from 'svelte/store';
import { consentGiven, profile, inference, resetSession } from './session';

describe('session stores', () => {
	it('default to empty/ephemeral state', () => {
		resetSession();
		expect(get(consentGiven)).toBe(false);
		expect(get(profile)).toBeNull();
		expect(get(inference)).toBeNull();
	});
	it('resetSession clears everything', () => {
		consentGiven.set(true);
		inference.set({ emotion_probs: { sad: 1 }, valence: -0.7, arousal: -0.5, zone: 'NEG_DEACTIVE' });
		resetSession();
		expect(get(consentGiven)).toBe(false);
		expect(get(inference)).toBeNull();
	});
});
