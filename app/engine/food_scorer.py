"""
Scores a list of food records from DB against a NeedVector.
Uses pre-computed normalization_cache from DB.
All scoring done in-memory after DB fetch — no per-row SQL computation.

Scoring formula S(f):
    n̂ᵢ(f) = (nᵢ(f) − min) / (max − min + ε)

    antox(f)  = 0.6 · n̂_vitC(f) + 0.4 · n̂_vitE(f)
    bvit(f)   = (n̂_B12(f) + n̂_folate(f)) / 2

    S(f) = w_trp · n̂_trp + w_om3 · n̂_om3 + w_carb · n̂_carb
         + w_mag · n̂_mag + w_fe · n̂_fe  + w_bvit · bvit
         + w_antx · antox + w_prot · n̂_prot + w_fib · n̂_fib
         − p_sug · n̂_sug

    NULL nutrients → treated as 0 (conservative, not imputed)
"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.need_vector import NeedVector

EPS = 1e-8


def _normalize(value, min_val: float, max_val: float) -> float:
    """Min-max normalize a single value; returns 0 if NULL or out of range."""
    if value is None:
        return 0.0
    rng = max_val - min_val + EPS
    return max(0.0, min(1.0, (float(value) - min_val) / rng))


def _top_contributors(norm_vals: dict, need: NeedVector) -> list[str]:
    """Return top-3 nutrient names by weighted contribution to score."""
    contributions = {
        "Tryptophan":    need.tryptophan    * norm_vals.get("tryptophan_mg", 0),
        "Omega-3":       need.omega3        * norm_vals.get("omega3_mg", 0),
        "Complex Carbs": need.complex_carbs * norm_vals.get("complex_carbs_g", 0),
        "Magnesium":     need.magnesium     * norm_vals.get("magnesium_mg", 0),
        "Iron":          need.iron          * norm_vals.get("iron_mg", 0),
        "B Vitamins":    need.b_vitamins    * norm_vals.get("bvit", 0),
        "Antioxidants":  need.antioxidants  * norm_vals.get("antox", 0),
        "Protein":       need.protein       * norm_vals.get("protein_g", 0),
        "Fiber":         need.fiber         * norm_vals.get("fiber_g", 0),
    }
    sorted_contribs = sorted(contributions.items(), key=lambda x: x[1], reverse=True)
    return [name for name, val in sorted_contribs[:3] if val > 0]


def score_foods(
    foods: list[dict],
    need: NeedVector,
    norm_cache: dict,
) -> list[dict]:
    """
    Score each food in-memory against the NeedVector.

    norm_cache format: {nutrient_key: {"min": float, "max": float}}
    Returns: foods list with added keys 'affective_score', 'top_contributors'
    """

    def nc(key: str):
        entry = norm_cache.get(key, {})
        return entry.get("min", 0.0), entry.get("max", 1.0)

    scored = []
    for food in foods:
        # Normalize each nutrient
        nv = {}
        nv["tryptophan_mg"]   = _normalize(food.get("tryptophan_mg"),   *nc("tryptophan_mg"))
        nv["omega3_mg"]       = _normalize(food.get("omega3_mg"),       *nc("omega3_mg"))
        nv["complex_carbs_g"] = _normalize(food.get("complex_carbs_g"), *nc("complex_carbs_g"))
        nv["magnesium_mg"]    = _normalize(food.get("magnesium_mg"),    *nc("magnesium_mg"))
        nv["iron_mg"]         = _normalize(food.get("iron_mg"),         *nc("iron_mg"))
        nv["protein_g"]       = _normalize(food.get("protein_g"),       *nc("protein_g"))
        nv["fiber_g"]         = _normalize(food.get("fiber_g"),         *nc("fiber_g"))
        nv["sugar_g"]         = _normalize(food.get("sugar_g"),         *nc("sugar_g"))
        # B-vitamin composite
        b12_n   = _normalize(food.get("vitamin_b12_mcg"), *nc("vitamin_b12_mcg"))
        folate_n = _normalize(food.get("folate_mcg"),     *nc("folate_mcg"))
        nv["bvit"] = (b12_n + folate_n) / 2.0
        # Antioxidant composite
        vitc_n = _normalize(food.get("vitamin_c_mg"), *nc("vitamin_c_mg"))
        vite_n = _normalize(food.get("vitamin_e_mg"), *nc("vitamin_e_mg"))
        nv["antox"] = 0.6 * vitc_n + 0.4 * vite_n

        score = (
            need.tryptophan    * nv["tryptophan_mg"]
            + need.omega3        * nv["omega3_mg"]
            + need.complex_carbs * nv["complex_carbs_g"]
            + need.magnesium     * nv["magnesium_mg"]
            + need.iron          * nv["iron_mg"]
            + need.b_vitamins    * nv["bvit"]
            + need.antioxidants  * nv["antox"]
            + need.protein       * nv["protein_g"]
            + need.fiber         * nv["fiber_g"]
            - need.sugar_penalty * nv["sugar_g"]
        )

        food_copy = dict(food)
        food_copy["affective_score"]  = round(score, 6)
        food_copy["top_contributors"] = _top_contributors(nv, need)
        scored.append(food_copy)

    return scored
