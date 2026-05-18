"""
Stage 3: Zone → Nutritional Need Vector (NNV).

Maps an emotional zone to:
  - Zone-specific macro percentage ratios (carb/prot/fat) within USDA AMDR bounds
  - Per-meal macro gram targets computed from the meal energy target
  - Zone-specific macro weights for ENMS scoring
  - Informational micronutrient priorities (display only, NOT in ENMS score)

All macro ratios are grounded in cited peer-reviewed research:
  Wurtman & Wurtman (1995) — carbohydrate → serotonin (Q2, Q3)
  Benton (2002) — blood glucose → mood stabilization (Q3)
  Macht (2008) — emotion × eating behaviour model (Q1)
  Jacka et al. (2017) — Mediterranean diet → mood (Q4)
  USDA AMDR bounds: carb 45–65%, protein 10–35%, fat 20–35%

See plan/formula_plan.md for full citation list.
"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import dataclass, field
from config import (
    ZONE_MACRO_RATIOS,
    ZONE_MACRO_WEIGHTS,
    ZONE_MICRONUTRIENT_PRIORITIES,
    DEFAULT_MEAL_KCAL,
)


@dataclass
class NeedVector:
    zone: str
    meal_kcal: float
    carb_pct: float
    prot_pct: float
    fat_pct: float
    carb_g: float           # (carb_pct × meal_kcal) / 4 kcal·g⁻¹
    prot_g: float           # (prot_pct × meal_kcal) / 4 kcal·g⁻¹
    fat_g: float            # (fat_pct  × meal_kcal) / 9 kcal·g⁻¹
    macro_weights: dict     # {"carb": float, "prot": float, "fat": float}
    micronutrient_priorities: list = field(default_factory=list)  # informational only


def compute_need_vector(zone: str, meal_kcal: float = None) -> NeedVector:
    """
    Stage 3: Compute NeedVector from emotional zone and per-meal energy target.

    carb_g = carb_pct × meal_kcal / 4   (4 kcal per gram of carbohydrate)
    prot_g = prot_pct × meal_kcal / 4   (4 kcal per gram of protein)
    fat_g  = fat_pct  × meal_kcal / 9   (9 kcal per gram of fat)

    If meal_kcal is None or ≤ 0, DEFAULT_MEAL_KCAL is used (profile-free fallback).
    """
    if not meal_kcal or meal_kcal <= 0:
        meal_kcal = DEFAULT_MEAL_KCAL

    ratios = ZONE_MACRO_RATIOS[zone]
    weights = ZONE_MACRO_WEIGHTS[zone]
    priorities = ZONE_MICRONUTRIENT_PRIORITIES.get(zone, [])

    return NeedVector(
        zone=zone,
        meal_kcal=meal_kcal,
        carb_pct=ratios["carb"],
        prot_pct=ratios["prot"],
        fat_pct=ratios["fat"],
        carb_g=round(ratios["carb"] * meal_kcal / 4, 1),
        prot_g=round(ratios["prot"] * meal_kcal / 4, 1),
        fat_g=round(ratios["fat"]  * meal_kcal / 9, 1),
        macro_weights=dict(weights),
        micronutrient_priorities=list(priorities),
    )


def need_vector_from_emotion(emotion_label: str, meal_kcal: float = None) -> NeedVector:
    """Convenience: emotion string → zone → NeedVector."""
    from engine.zone_classifier import zone_from_emotion
    zone = zone_from_emotion(emotion_label)
    return compute_need_vector(zone, meal_kcal)


def need_vector_to_dict(nv: NeedVector) -> dict:
    """Serialize NeedVector to dict for display/logging."""
    return {
        "zone":     nv.zone,
        "meal_kcal": nv.meal_kcal,
        "carb_pct": nv.carb_pct,
        "prot_pct": nv.prot_pct,
        "fat_pct":  nv.fat_pct,
        "carb_g":   nv.carb_g,
        "prot_g":   nv.prot_g,
        "fat_g":    nv.fat_g,
        "macro_weights":           nv.macro_weights,
        "micronutrient_priorities": nv.micronutrient_priorities,
    }
