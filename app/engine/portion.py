"""
Stage 4 helper: Portion-adjusted nutrient calculation.

nutrient_actual = nutrient_per100g × (portion_g / 100)

Default portions per category align with formula_plan.md §4.2:
  main_dish  = 300g
  side_dish  = 150g
  soup/stew  = 250g
  salad      = 200g
"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DEFAULT_PORTIONS_G, DEFAULT_PORTION_G


def default_portion_g(food: dict) -> float:
    """
    Determine the default portion size in grams for a food item.

    Checks food['category'] and food['meal_type'] against DEFAULT_PORTIONS_G keys.
    Falls back to food['serving_size_g'] if present, then DEFAULT_PORTION_G.
    """
    text = " ".join(filter(None, [
        str(food.get("category") or ""),
        str(food.get("meal_type") or ""),
    ])).lower()

    for key, grams in DEFAULT_PORTIONS_G.items():
        if key.replace("_", " ") in text or key in text:
            return float(grams)

    serving = food.get("serving_size_g")
    if serving and float(serving) > 0:
        return float(serving)

    return float(DEFAULT_PORTION_G)


def portion_adjusted(nutrient_per100g, portion_g: float) -> float:
    """
    Return actual nutrient amount for the given portion.
    None-safe: returns 0.0 if nutrient_per100g is None.

    nutrient_actual = nutrient_per100g × (portion_g / 100)
    """
    if nutrient_per100g is None:
        return 0.0
    return float(nutrient_per100g) * portion_g / 100.0
