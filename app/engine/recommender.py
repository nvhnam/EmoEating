"""
Stage 4–5 Orchestrator: ENMS recommendation pipeline.
Single entry point called by the Streamlit recommendation page.

Pipeline:
  1. Emotion → (V, A) → Zone  [OR: pre-computed zone from SER, bypasses VA step]
  2. meal_energy_target(tdee, meal_type)  → meal_kcal
  3. compute_need_vector(zone, meal_kcal) → NeedVector
  4. get_meals(meal_type, restrictions)   → foods[]
  5. score_foods(foods, need)             → macro_score + micro_score per food
  6. pref_score = DEFAULT_PREF_SCORE (0.5 stub)
  7. ENMS = α·macro_score + β·micro_score + γ·pref_score
       α = ENMS_MACRO_ALPHA = 0.55
       β = ENMS_MICRO_BETA  = 0.20
       γ = 1 − α − β       = 0.25
  8. sort descending, take top_k, assign rank

References: guide.md Phase 5; Russell (1980); Mifflin-St Jeor (1990);
            NIH ODS DRI 2020; Wurtman & Wurtman (1995); Jacka et al. (2017).
"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Optional

from engine.affect_mapper import emotion_to_va
from engine.zone_classifier import classify_zone
from engine.need_vector import compute_need_vector
from engine.food_scorer import score_foods
from engine.physiological import PhysiologicalProfile, meal_energy_target
from config import (
    ENMS_MACRO_ALPHA,
    ENMS_MICRO_BETA,
    DEFAULT_PREF_SCORE,
    TOP_K_DEFAULT,
    MEAL_ENERGY_FRACTION,
)


def get_recommendations(
    emotion: str,
    meal_type: str,
    user_profile: Optional[PhysiologicalProfile],
    dietary_restrictions: list[str],
    top_k: int = TOP_K_DEFAULT,
    db_conn=None,
    zone: str = None,
) -> list[dict]:
    """
    Full ENMS recommendation pipeline.

    Args:
      emotion  : Emotion label string (manual selection).
      zone     : Pre-computed zone from SER inference. If provided, overrides
                 the VA-based zone classification (guide.md Phase 6.1).

    Returns up to top_k food dicts, each with:
      enms, final_score, macro_score, micro_score, pref_score,
      macro_breakdown, micronutrient_coverage, top_macros,
      zone, emotion_V, emotion_A, rank
    """
    from db.queries import get_meals

    # Stage 1–2: Emotion → (V, A) → Zone
    # SER path: zone is pre-computed; still try to derive VA for display.
    try:
        V, A = emotion_to_va(emotion)
    except ValueError:
        V, A = 0.0, 0.0   # SER emotion not in manual EMOTION_COORDS — use origin

    if zone is None:
        zone = classify_zone(V, A)

    # Stage 3: Per-meal energy target
    meal_kcal = None
    if user_profile:
        meal_kcal = meal_energy_target(user_profile.tdee_kcal, meal_type)

    # Stage 4: Zone + meal_kcal → NeedVector
    need = compute_need_vector(zone, meal_kcal)

    user_sex = user_profile.sex if user_profile else "male"
    meal_fraction = MEAL_ENERGY_FRACTION.get(meal_type.lower(), 1 / 3)

    # Stage 5a: Fetch candidate foods (dietary hard filter applied in SQL)
    foods = get_meals(
        meal_type=meal_type,
        dietary_restrictions=dietary_restrictions,
        db_conn=db_conn,
    )
    if not foods:
        return []

    # Stage 5b: Score foods — macro_score + micro_score + coverage per food
    scored = score_foods(foods, need, user_sex=user_sex, meal_fraction=meal_fraction)

    # Stage 5c: Blend → ENMS
    pref_weight = 1.0 - ENMS_MACRO_ALPHA - ENMS_MICRO_BETA  # γ = 0.25
    for food in scored:
        pref = DEFAULT_PREF_SCORE  # 0.5 neutral prior; extend with interaction history
        enms = round(
            ENMS_MACRO_ALPHA * food["macro_score"]
            + ENMS_MICRO_BETA  * food["micro_score"]
            + pref_weight      * pref,
            6,
        )
        food["pref_score"]  = pref
        food["enms"]        = enms
        food["final_score"] = enms   # alias for display compatibility
        food["zone"]        = zone
        food["emotion_V"]   = V
        food["emotion_A"]   = A

    # Stage 5d: Sort and return top_k
    scored.sort(key=lambda f: f["enms"], reverse=True)
    results = scored[:top_k]
    for rank, food in enumerate(results, start=1):
        food["rank"] = rank

    return results
