"""
Orchestrator: combines affective scoring + physiological profile.
Single entry point called by the Streamlit recommendation page.

Final score = AFFECTIVE_WEIGHT * affective_score
            + CALORIC_WEIGHT   * caloric_proximity_score  (if profile present)
"""

from __future__ import annotations
from typing import Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.affect_mapper import emotion_to_va
from engine.need_vector import compute_need_vector
from engine.food_scorer import score_foods
from engine.physiological import PhysiologicalProfile
from config import AFFECTIVE_WEIGHT, CALORIC_WEIGHT, TOP_K_DEFAULT


def _caloric_proximity(food_kcal: Optional[float], target_kcal: float) -> float:
    """
    Returns a score ∈ [0, 1] representing how close food_kcal is to target.
    1.0 = perfect match, 0.0 = ≥100% away.
    """
    if food_kcal is None or target_kcal <= 0:
        return 0.5  # neutral if unknown
    deviation = abs(float(food_kcal) - target_kcal) / target_kcal
    return max(0.0, 1.0 - deviation)


def get_recommendations(
    emotion: str,
    meal_type: str,
    user_profile: Optional[PhysiologicalProfile],
    dietary_restrictions: list[str],
    top_k: int = TOP_K_DEFAULT,
    db_conn=None,
) -> list[dict]:
    """
    Full recommendation pipeline:
    1. affect_mapper.emotion_to_va → (V, A)
    2. need_vector.compute_need_vector → NeedVector
    3. db.queries.get_meals → candidate foods[]
    4. food_scorer.score_foods → affective_score per food
    5. caloric_proximity_score if user_profile set
    6. final_score blend → sort → top_k
    7. (logging handled by caller via session_logger)
    """
    from db.queries import get_meals, get_normalization_cache

    V, A = emotion_to_va(emotion)
    need = compute_need_vector(V, A)

    kcal_min = None
    kcal_max = None
    meal_kcal_target = None
    if user_profile:
        meal_kcal_target = user_profile.meal_kcal_target
        from config import CALORIC_TOLERANCE
        kcal_min = meal_kcal_target * (1.0 - CALORIC_TOLERANCE)
        kcal_max = meal_kcal_target * (1.0 + CALORIC_TOLERANCE)

    from config import MIN_DATA_COMPLETENESS
    foods = get_meals(
        meal_type=meal_type,
        dietary_restrictions=dietary_restrictions,
        min_completeness=MIN_DATA_COMPLETENESS,
        kcal_min=kcal_min,
        kcal_max=kcal_max,
        db_conn=db_conn,
    )

    if not foods:
        return []

    norm_cache = get_normalization_cache(db_conn=db_conn)
    scored = score_foods(foods, need, norm_cache)

    if user_profile and meal_kcal_target:
        for food in scored:
            cal_score = _caloric_proximity(food.get("calories_kcal"), meal_kcal_target)
            food["caloric_proximity_score"] = round(cal_score, 4)
            food["final_score"] = round(
                AFFECTIVE_WEIGHT * food["affective_score"]
                + CALORIC_WEIGHT  * cal_score,
                6,
            )
    else:
        for food in scored:
            food["caloric_proximity_score"] = None
            food["final_score"] = food["affective_score"]

    scored.sort(key=lambda f: f["final_score"], reverse=True)
    results = scored[:top_k]

    for rank, food in enumerate(results, start=1):
        food["rank"] = rank

    return results
