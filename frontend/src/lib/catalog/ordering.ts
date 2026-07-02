import type { FoodOut, MealOut, RecommendResult } from '$lib/api';

export interface CatalogEntry {
	food: FoodOut;
	meal: MealOut | null;
}

// Recommended dishes first (already in score order from the API), the rest of the
// catalog in its default order. Nothing is hidden — re-rank + badge, not filter.
export function deriveOrder(catalog: FoodOut[], rec: RecommendResult | null): CatalogEntry[] {
	if (!rec) return catalog.map((food) => ({ food, meal: null }));
	const matchedIds = new Set(rec.meals.map((m) => m.food.id));
	const byId = new Map(catalog.map((f) => [f.id, f]));
	const matched = rec.meals.map((meal) => ({ food: byId.get(meal.food.id) ?? meal.food, meal }));
	const rest = catalog.filter((f) => !matchedIds.has(f.id)).map((food) => ({ food, meal: null }));
	return [...matched, ...rest];
}
