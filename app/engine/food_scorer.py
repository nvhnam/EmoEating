"""
Stage 4: ENMS macro fulfillment scorer.

ENMS(F, Z, U) = α × macro_score(F, Z, U) + (1−α) × pref_score(F, U)

macro_score(F, Z, U) = Σ_{m ∈ {carb, prot, fat}} [
    w_m^Zone × min( actual_m(F) / target_m(Z, U), 1.0 )
]

where:
  actual_m(F) = portion_adjusted(nutrient_per100g_m, portion_g)
  target_m(Z, U) = NeedVector gram target for macro m
  w_m^Zone = zone-specific macro weight (sums to 1.0)
  min(·, 1.0) caps fulfillment — exceeding target gives no extra credit

Micronutrients: informational display ONLY.
  - Used in micronutrient_coverage() for UI context ("good source of …")
  - NULL nutrient fields → skipped silently, NOT penalized
  - Never affect macro_score or ENMS

Dietary restriction hard filter is applied upstream in get_meals() (SQL).

References: formula_plan.md §4.3–4.5; Mifflin-St Jeor (1990); Russell (1980);
            NIH ODS DRI 2020 for RDA reference values.
"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.need_vector import NeedVector
from engine.portion import default_portion_g, portion_adjusted
from config import RDA_REFERENCE, NUTRIENT_DISPLAY_LABELS

_MACRO_COLS = {
    "carb": "carbohydrate_g",
    "prot": "protein_g",
    "fat":  "fat_g",
}

_MACRO_LABELS = {
    "carb": "Carbs",
    "prot": "Protein",
    "fat":  "Fat",
}


def macro_score(
    food: dict,
    need: NeedVector,
    portion_g: float,
) -> tuple[float, dict]:
    """
    Compute macro fulfillment score for a single food item.

    Returns:
      score   : float ∈ [0, 1]
      breakdown: dict mapping macro → {actual_g, target_g, ratio, contribution, label}
    """
    targets = {"carb": need.carb_g, "prot": need.prot_g, "fat": need.fat_g}
    weights = need.macro_weights

    total = 0.0
    breakdown = {}

    for macro, col in _MACRO_COLS.items():
        actual = portion_adjusted(food.get(col), portion_g)
        target = targets[macro]
        ratio = min(actual / target, 1.0) if target > 0 else 0.0
        w = weights[macro]
        contrib = w * ratio
        total += contrib
        breakdown[macro] = {
            "label":        _MACRO_LABELS[macro],
            "actual_g":     round(actual, 1),
            "target_g":     target,
            "ratio":        round(ratio, 3),
            "contribution": round(contrib, 4),
        }

    return round(total, 6), breakdown


def micronutrient_coverage(
    food: dict,
    zone: str,
    sex: str,
    meal_fraction: float,
) -> dict:
    """
    INFORMATIONAL ONLY. Compute actual vs per-meal RDA for zone-priority micronutrients.

    NULL fields are silently skipped (not penalized, logged in 'missing').
    Never used in ENMS calculation.

    Returns:
      {
        "covered": [{"nutrient", "label", "actual", "meal_target", "pct_of_meal_target"}, ...],
        "missing": [nutrient_col, ...]
      }
    """
    from config import ZONE_MICRONUTRIENT_PRIORITIES
    sex_key = "female" if sex == "female" else "male"
    priorities = ZONE_MICRONUTRIENT_PRIORITIES.get(zone, [])

    covered = []
    missing = []

    for col in priorities:
        rda_by_sex = RDA_REFERENCE.get(col)
        if rda_by_sex is None:
            continue
        val = food.get(col)
        rda_day = rda_by_sex[sex_key]
        meal_target = rda_day * meal_fraction

        if val is None or float(val) == 0.0:
            missing.append(col)
        else:
            actual = float(val)
            pct = round(actual / meal_target * 100, 1) if meal_target > 0 else 0.0
            covered.append({
                "nutrient":          col,
                "label":             NUTRIENT_DISPLAY_LABELS.get(col, col),
                "actual":            round(actual, 2),
                "meal_target":       round(meal_target, 3),
                "pct_of_meal_target": pct,
            })

    return {"covered": covered, "missing": missing}


def score_foods(
    foods: list[dict],
    need: NeedVector,
    user_sex: str = "male",
    meal_fraction: float = 0.33,
) -> list[dict]:
    """
    Score each food against the NeedVector using ENMS macro fulfillment.

    Dietary restriction hard filter must be applied upstream (in get_meals).

    Adds to each food dict:
      portion_g            : float  — portion used for nutrient calculation
      macro_score          : float  — ∈ [0, 1]
      macro_breakdown      : dict   — per-macro {actual_g, target_g, ratio, contribution, label}
      micronutrient_coverage: dict  — {covered: [...], missing: [...]}
      top_macros           : list   — macro keys sorted by contribution (for UI chips)
    """
    scored = []

    for food in foods:
        portion_g = default_portion_g(food)
        m_score, breakdown = macro_score(food, need, portion_g)
        micro_cov = micronutrient_coverage(food, need.zone, user_sex, meal_fraction)

        top_macros = sorted(
            breakdown.keys(),
            key=lambda m: breakdown[m]["contribution"],
            reverse=True,
        )

        food_copy = dict(food)
        food_copy["portion_g"]             = portion_g
        food_copy["macro_score"]           = m_score
        food_copy["macro_breakdown"]       = breakdown
        food_copy["micronutrient_coverage"] = micro_cov
        food_copy["top_macros"]            = top_macros
        scored.append(food_copy)

    return scored
