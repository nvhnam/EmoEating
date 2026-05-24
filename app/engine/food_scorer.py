"""
Stage 4: ENMS scorer — 3-component hybrid formula.

ENMS(F, Z, U) = α × macro_score(F, Z, U)
              + β × micro_score(F, Z, U)
              + γ × pref_score(F, U)

  α = ENMS_MACRO_ALPHA = 0.55
  β = ENMS_MICRO_BETA  = 0.20
  γ = 1 - α - β       = 0.25

macro_score(F, Z, U) = Σ_{m ∈ {carb, prot, fat}} [
    w_m^Zone × min( actual_m(F) / target_m(Z, U), 1.0 )
]

micro_score(F, Z, U) = (1/|N_Z|) × Σ_{n ∈ N_Z} min( actual_n(F) / target_n(U), 1.0 )
  where actual_n = portion_adjusted(food[n], portion_g)  [0 if NULL or 0.0]
        target_n = RDA_REFERENCE[n][sex] × meal_fraction
  Every zone has |N_Z| ≥ 2 (guide.md Phase 4.2) → score always well-defined.

Why "NULL → 0" and not skip-and-renormalise:
  Skipping would allow a food reporting only one micronutrient to score 1.0, gaming
  the ranking. The conservative rule credits a food only for what it can verifiably
  provide. The β=0.20 weight ceiling limits the penalty to at most 0.20 of ENMS.

Dietary restriction hard filter is applied upstream in get_meals() (SQL).

References: Wurtman & Wurtman (1995); Boyle et al. (2017); Kennedy (2016);
            Jacka et al. (2017); Cryan et al. (2019); Gomez-Pinilla (2008);
            NIH ODS DRI 2020; Mifflin-St Jeor (1990); Russell (1980).
"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.need_vector import NeedVector
from engine.portion import default_portion_g, portion_adjusted
from config import (
    RDA_REFERENCE,
    NUTRIENT_DISPLAY_LABELS,
    ZONE_MICRONUTRIENT_PRIORITIES,
)

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
      score    : float ∈ [0, 1]
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


def micro_score(
    food: dict,
    zone: str,
    sex: str,
    meal_fraction: float,
    portion_g: float,
) -> float:
    """
    Zone-priority micronutrient fulfillment score (β component of ENMS).

    Returns float ∈ [0, 1]:
      (1/|N_Z|) × Σ_{n ∈ N_Z} min(actual_n / target_n, 1.0)

    actual_n = portion_adjusted(food[n], portion_g)  — 0 if NULL or 0.0
    target_n = RDA_REFERENCE[n][sex] × meal_fraction

    Every zone has |N_Z| ≥ 2 (guide.md Phase 4.2) → always well-defined.
    NULL values → 0 (conservative; avoids score gaming by partial reporters).
    """
    priorities = ZONE_MICRONUTRIENT_PRIORITIES.get(zone, [])
    if not priorities:
        return 0.0

    sex_key = "female" if sex == "female" else "male"
    total = 0.0

    for col in priorities:
        rda_by_sex = RDA_REFERENCE.get(col)
        if rda_by_sex is None:
            continue
        meal_target = rda_by_sex[sex_key] * meal_fraction
        if meal_target <= 0:
            continue
        raw_val = food.get(col)
        actual = portion_adjusted(raw_val, portion_g) if raw_val else 0.0
        total += min(actual / meal_target, 1.0)

    return round(total / len(priorities), 6)


def micronutrient_coverage(
    food: dict,
    zone: str,
    sex: str,
    meal_fraction: float,
) -> dict:
    """
    INFORMATIONAL ONLY. Compute actual vs per-meal RDA for zone-priority micronutrients.

    NULL fields are silently skipped (not penalized, logged in 'missing').
    Never used in ENMS calculation — this is the explainability display only.

    Returns:
      {
        "covered": [{"nutrient", "label", "actual", "meal_target", "pct_of_meal_target"}, ...],
        "missing": [nutrient_col, ...]
      }
    """
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
                "nutrient":           col,
                "label":              NUTRIENT_DISPLAY_LABELS.get(col, col),
                "actual":             round(actual, 2),
                "meal_target":        round(meal_target, 3),
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
    Score each food against the NeedVector.

    Dietary restriction hard filter must be applied upstream (in get_meals).

    Adds to each food dict:
      portion_g             : float — portion used for nutrient calculation
      macro_score           : float — ∈ [0, 1]
      micro_score           : float — ∈ [0, 1] — zone-priority micro fulfillment
      macro_breakdown       : dict  — per-macro {actual_g, target_g, ratio, contribution, label}
      micronutrient_coverage: dict  — {covered: [...], missing: [...]}
      top_macros            : list  — macro keys sorted by contribution (for UI chips)
    """
    scored = []

    for food in foods:
        portion_g = default_portion_g(food)
        m_score, breakdown = macro_score(food, need, portion_g)
        m_micro = micro_score(food, need.zone, user_sex, meal_fraction, portion_g)
        micro_cov = micronutrient_coverage(food, need.zone, user_sex, meal_fraction)

        top_macros = sorted(
            breakdown.keys(),
            key=lambda m: breakdown[m]["contribution"],
            reverse=True,
        )

        food_copy = dict(food)
        food_copy["portion_g"]              = portion_g
        food_copy["macro_score"]            = m_score
        food_copy["micro_score"]            = m_micro
        food_copy["macro_breakdown"]        = breakdown
        food_copy["micronutrient_coverage"] = micro_cov
        food_copy["top_macros"]             = top_macros
        scored.append(food_copy)

    return scored
