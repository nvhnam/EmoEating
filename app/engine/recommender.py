"""
Stage 4–5 Orchestrator: ENMS recommendation pipeline.
Single entry point called by the Streamlit recommendation page.

Pipeline:
  1. Emotion → (V, A) → Zone  [OR: pre-computed zone from SER, bypasses VA step]
  2. meal_energy_target(tdee, meal_type)  → meal_kcal
  3. compute_need_vector(zone, meal_kcal) → NeedVector
  4. get_meals(meal_type, restrictions)   → foods[]
  5. Two-phase scoring with priority queue:
       Phase A — PRIMARY:  foods with ALL zone-priority micronutrients non-null
                           → scored, sorted, deduplicated → fills up to top_k slots
       Phase B — FALLBACK: only if primary yields < top_k unique results
                           foods with ANY zone-priority micronutrient non-null
                           (excludes foods already in the primary pool)
                           → scored, sorted, deduplicated → fills remaining slots
  6. pref_score = DEFAULT_PREF_SCORE (0.5 stub)
  7. ENMS = α·macro_score + β·micro_score + γ·pref_score
       α = ENMS_MACRO_ALPHA = 0.55
       β = ENMS_MICRO_BETA  = 0.20
       γ = 1 − α − β       = 0.25
  8. Final ranks assigned across both phases in order (primary first)

References: guide.md Phase 5; Russell (1980); Mifflin-St Jeor (1990);
            NIH ODS DRI 2020; Wurtman & Wurtman (1995); Jacka et al. (2017).
"""

from __future__ import annotations

import re
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
    MIN_DATA_COMPLETENESS,
    NUTRIENT_NULL,
    ZONE_MICRONUTRIENT_PRIORITIES,
    RECOMMENDATION_BLOCKLIST,
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
    Full ENMS recommendation pipeline with two-phase priority scoring.

    Phase A (primary): foods where ALL zone-priority micronutrients are non-null.
    These are the highest-quality candidates — they can be fully scored on every
    ENMS component.  Up to top_k results are drawn from this pool first.

    Phase B (fallback): activated only when Phase A yields fewer than top_k unique
    results.  Draws from foods that have AT LEAST ONE zone-priority micronutrient
    non-null (excluding foods already in the primary pool).  Missing nutrients
    score 0 in micro_score() per the NULL→0 rule (guide.md §4.2).

    Name-based deduplication is applied within each phase so that duplicate DB
    entries (e.g. 'Smoked Salmon' × 3) never occupy multiple recommendation slots.

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
    try:
        V, A = emotion_to_va(emotion)
    except ValueError:
        V, A = 0.0, 0.0

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

    # Stage 5a: Fetch all candidate foods (dietary hard filter in SQL)
    foods = get_meals(
        meal_type=meal_type,
        dietary_restrictions=dietary_restrictions,
        min_completeness=MIN_DATA_COMPLETENESS,
        db_conn=db_conn,
    )
    if not foods:
        return []

    # Stage 5a-blocklist: remove foods with known incorrect nutrient data.
    # Entries are managed in config.py RECOMMENDATION_BLOCKLIST.
    # Matching is exact and case-insensitive; remove an entry once the ETL is fixed.
    if RECOMMENDATION_BLOCKLIST:
        _blocked = {n.lower().strip() for n in RECOMMENDATION_BLOCKLIST}
        foods = [
            f for f in foods
            if (f.get("name") or "").lower().strip() not in _blocked
        ]
    if not foods:
        return []

    # Stage 5b: Split into primary and fallback pools
    # When NUTRIENT_NULL=True (dev/test flag) skip all micro-filtering and
    # score everything in a single pass — consistent with original bypass intent.
    if NUTRIENT_NULL:
        results = _score_blend_dedup(foods, need, user_sex, meal_fraction,
                                     zone, V, A, top_k)
    else:
        zone_micros = ZONE_MICRONUTRIENT_PRIORITIES.get(zone, [])

        if not zone_micros:
            # Zone has no defined micronutrient priorities — score everything
            results = _score_blend_dedup(foods, need, user_sex, meal_fraction,
                                         zone, V, A, top_k)
        else:
            # PRIMARY pool: all zone-priority micronutrients present
            primary_foods = [
                f for f in foods
                if all(f.get(col) is not None for col in zone_micros)
            ]

            # Score primary pool
            primary_results = _score_blend_dedup(
                primary_foods, need, user_sex, meal_fraction, zone, V, A, top_k
            )

            if len(primary_results) >= top_k:
                # Primary pool filled every slot — no fallback needed
                results = primary_results
            else:
                # FALLBACK pool: at least one zone-priority micronutrient present,
                # but excludes every food already in the primary pool (by food ID)
                # so no food is scored or dedup-checked twice.
                primary_ids = {f.get("id") for f in primary_foods}
                fallback_foods = [
                    f for f in foods
                    if f.get("id") not in primary_ids
                    and any(f.get(col) is not None for col in zone_micros)
                ]

                remaining = top_k - len(primary_results)
                # Pass already-seen name keys so fallback dedup respects primary names
                seen_keys = {_name_key(f.get("name") or "") for f in primary_results}
                fallback_results = _score_blend_dedup(
                    fallback_foods, need, user_sex, meal_fraction, zone, V, A,
                    remaining, excluded_keys=seen_keys
                )

                results = primary_results + fallback_results

    # Stage 5c: Assign final ranks (primary slots first, then fallback)
    for rank, food in enumerate(results, start=1):
        food["rank"] = rank

    return results


# ── Internal helpers ──────────────────────────────────────────────────────────

def _score_blend_dedup(
    foods: list[dict],
    need,
    user_sex: str,
    meal_fraction: float,
    zone: str,
    V: float,
    A: float,
    top_k: int,
    excluded_keys: set[str] | None = None,
) -> list[dict]:
    """
    Score foods against the NeedVector, blend into ENMS, sort descending,
    apply name-based deduplication, and return up to top_k results.

    excluded_keys: name keys already committed in a previous phase; foods
    matching these keys are skipped during deduplication.
    """
    if not foods:
        return []

    pref_weight = 1.0 - ENMS_MACRO_ALPHA - ENMS_MICRO_BETA  # γ = 0.25
    scored = score_foods(foods, need, user_sex=user_sex, meal_fraction=meal_fraction)

    for food in scored:
        pref = DEFAULT_PREF_SCORE
        enms = round(
            ENMS_MACRO_ALPHA * food["macro_score"]
            + ENMS_MICRO_BETA  * food["micro_score"]
            + pref_weight      * pref,
            6,
        )
        food["pref_score"]  = pref
        food["enms"]        = enms
        food["final_score"] = enms
        food["zone"]        = zone
        food["emotion_V"]   = V
        food["emotion_A"]   = A

    scored.sort(key=lambda f: f["enms"], reverse=True)
    return _deduplicate_top_k(scored, top_k, excluded_keys=excluded_keys)


def _name_key(name: str) -> str:
    """
    Normalised 2-word deduplication key.
    Strips punctuation, lowercases, takes the first two words so that
    near-identical DB entries ('Smoked Salmon' / 'Smoked Salmon Fillet',
    'Butter' × 12) collapse to one key and only the best-scoring variant
    reaches the user.
    """
    clean = re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()
    words = clean.split()
    return " ".join(words[:2]) if words else ""


def _deduplicate_top_k(
    scored: list[dict],
    top_k: int,
    excluded_keys: set[str] | None = None,
) -> list[dict]:
    """
    Walk the ENMS-sorted list and collect up to top_k foods,
    skipping any food whose 2-word name key is already in seen.
    excluded_keys seeds seen so cross-phase dedup is respected.
    """
    seen: set[str] = set(excluded_keys or ())
    results: list[dict] = []
    for food in scored:
        key = _name_key(food.get("name") or "")
        if key not in seen:
            seen.add(key)
            results.append(food)
        if len(results) >= top_k:
            break
    return results
