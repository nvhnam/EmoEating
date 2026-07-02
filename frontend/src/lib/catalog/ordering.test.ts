import { describe, expect, it } from 'vitest';
import { deriveOrder } from './ordering';
import type { FoodOut, MealOut, RecommendResult } from '$lib/api';

const food = (id: string): FoodOut => ({ id, name: id, source: 's', calories: 100, image_hint: null });
const meal = (id: string, enms: number): MealOut => ({
	food: food(id),
	enms,
	m_macro: 0.5,
	m_micro: 0.5,
	satisfied_targets: []
});
const rec = (meals: MealOut[]): RecommendResult => ({
	meals,
	nnv: { zone: 'NEUTRAL_CALM', macro_targets: {}, macro_weights: {}, micro_targets: {}, priority_micros: [] }
});

describe('deriveOrder', () => {
	it('returns the catalog unbadged in default order without a recommendation', () => {
		const out = deriveOrder([food('a'), food('b')], null);
		expect(out.map((e) => e.food.id)).toEqual(['a', 'b']);
		expect(out.every((e) => e.meal === null)).toBe(true);
	});

	it('floats recommended dishes to the top in score order, rest keeps catalog order', () => {
		const catalog = [food('a'), food('b'), food('c'), food('d')];
		const out = deriveOrder(catalog, rec([meal('c', 0.9), meal('a', 0.8)]));
		expect(out.map((e) => e.food.id)).toEqual(['c', 'a', 'b', 'd']);
		expect(out[0].meal?.enms).toBe(0.9);
		expect(out[2].meal).toBeNull();
	});

	it('includes a recommended dish even if it is missing from the catalog page', () => {
		const out = deriveOrder([food('a')], rec([meal('zzz', 0.7)]));
		expect(out.map((e) => e.food.id)).toEqual(['zzz', 'a']);
	});
});
