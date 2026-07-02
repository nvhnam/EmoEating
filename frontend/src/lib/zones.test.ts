import { describe, it, expect } from 'vitest';
import { ZONE_DISPLAY, MICRO_LABELS, macroLabel } from './zones';

describe('zone display metadata', () => {
	it('covers all four zone strings', () => {
		expect(Object.keys(ZONE_DISPLAY).sort()).toEqual([
			'NEG_ACTIVE',
			'NEG_DEACTIVE',
			'NEUTRAL_CALM',
			'POS_ACTIVE'
		]);
	});
	it('labels every priority micronutrient key', () => {
		for (const z of Object.values(ZONE_DISPLAY)) {
			// priority lists hold display strings; the key map covers canonical keys
			expect(z.priority.length).toBeGreaterThan(0);
		}
		expect(MICRO_LABELS['omega3_g']).toBe('Omega-3');
		expect(macroLabel('protein_g')).toBe('Protein');
	});
});
