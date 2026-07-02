// The per-zone `priority` arrays mirror the backend's config.ZONE_PRIORITY_MICROS.
// They are only the pre-recommendation display fallback shown before an NNV exists;
// once the API returns an NNV its `priority_micros` wins (see NutrientTargets.svelte).
export const ZONE_DISPLAY: Record<string, { label: string; blurb: string; priority: string[] }> = {
	POS_ACTIVE: { label: 'Positive · Active', blurb: 'Upbeat and energised', priority: ['Vitamin C', 'Vitamin E'] },
	NEG_ACTIVE: { label: 'Negative · Active', blurb: 'Tense or agitated', priority: ['Magnesium', 'Vitamin B6', 'Vitamin C'] },
	NEG_DEACTIVE: { label: 'Negative · Low-energy', blurb: 'Low and depleted', priority: ['Folate', 'Vitamin B12', 'Vitamin D', 'Omega-3'] },
	NEUTRAL_CALM: { label: 'Calm · Neutral', blurb: 'Balanced baseline', priority: ['Fibre', 'Omega-3'] }
};

export const MICRO_LABELS: Record<string, string> = {
	vit_c_mg: 'Vitamin C',
	vit_e_mg: 'Vitamin E',
	magnesium_mg: 'Magnesium',
	vit_b6_mg: 'Vitamin B6',
	folate_ug: 'Folate',
	vit_b12_ug: 'Vitamin B12',
	vit_d_ug: 'Vitamin D',
	omega3_g: 'Omega-3',
	fiber_g: 'Fibre'
};

const MACRO_LABELS: Record<string, string> = {
	protein_g: 'Protein',
	carb_g: 'Carbs',
	fat_g: 'Fat'
};

export function macroLabel(key: string): string {
	return MACRO_LABELS[key] ?? key;
}

export function nutrientLabel(key: string): string {
	return MICRO_LABELS[key] ?? MACRO_LABELS[key] ?? key;
}
