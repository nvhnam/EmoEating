"""
Stage 4–5 Orchestrator: 5-stage ENMS recommendation pipeline.
Single entry point called by the Streamlit recommendation page.

Pipeline:
  1. emotion_to_va(emotion)             → (V, A)
  2. classify_zone(V, A)                → zone
  3. meal_energy_target(tdee, meal_type) → meal_kcal  (DEFAULT_MEAL_KCAL if no profile)
  4. compute_need_vector(zone, meal_kcal) → NeedVector
  5. get_meals(meal_type, restrictions)  → foods[]
  6. score_foods(foods, need)            → macro_score + micronutrient_coverage per food
  7. pref_score = DEFAULT_PREF_SCORE (0.5; stub — no user history table yet)
  8. ENMS = ENMS_ALPHA × macro_score + (1−ENMS_ALPHA) × pref_score
  9. sort descending, take top_k, assign rank

References: formula_plan.md; Russell (1980); Mifflin-St Jeor (1990);
            USDA Dietary Guidelines 2020–2025; NIH ODS DRI 2020.
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
from config import ENMS_ALPHA, DEFAULT_PREF_SCORE, TOP_K_DEFAULT, MEAL_ENERGY_FRACTION


def get_recommendations(
    emotion: str,
    meal_type: str,
    user_profile: Optional[PhysiologicalProfile],
    dietary_restrictions: list[str],
    top_k: int = TOP_K_DEFAULT,
    db_conn=None,
) -> list[dict]:
    """
    Full ENMS recommendation pipeline.

    Returns up to top_k food dicts, each with:
      enms, final_score, macro_score, pref_score, macro_breakdown,
      micronutrient_coverage, top_macros, zone, emotion_V, emotion_A, rank
    """
    from db.queries import get_meals

    # Stage 1–2: Emotion → (V, A) → Zone
    V, A = emotion_to_va(emotion)
    zone = classify_zone(V, A)

    # Stage 1: Per-meal energy target
    meal_kcal = None
    if user_profile:
        meal_kcal = meal_energy_target(user_profile.tdee_kcal, meal_type)

    # Stage 3: Zone + meal_kcal → NeedVector
    need = compute_need_vector(zone, meal_kcal)

    # Derived parameters for micronutrient coverage display
    user_sex = user_profile.sex if user_profile else "male"
    meal_fraction = MEAL_ENERGY_FRACTION.get(meal_type.lower(), 1 / 3)

    # Stage 4a: Fetch candidate foods (dietary hard filter applied in SQL)
    foods = get_meals(
        meal_type=meal_type,
        dietary_restrictions=dietary_restrictions,
        db_conn=db_conn,
    )
    if not foods:
        return []

    # Stage 4b: Score foods via macro fulfillment
    scored = score_foods(foods, need, user_sex=user_sex, meal_fraction=meal_fraction)

    # Stage 4c: Blend macro_score with pref_score → ENMS
    for food in scored:
        # pref_score stub: 0.5 neutral prior (no user history table yet)
        # Extension point: replace with interaction-history-based signal
        pref = DEFAULT_PREF_SCORE
        enms = round(ENMS_ALPHA * food["macro_score"] + (1 - ENMS_ALPHA) * pref, 6)
        food["pref_score"]   = pref
        food["enms"]         = enms
        food["final_score"]  = enms   # alias for backward compat with display code
        food["zone"]         = zone
        food["emotion_V"]    = V
        food["emotion_A"]    = A

    # Stage 4d: Sort and return top_k
    scored.sort(key=lambda f: f["enms"], reverse=True)
    results = scored[:top_k]
    for rank, food in enumerate(results, start=1):
        food["rank"] = rank

    return results
