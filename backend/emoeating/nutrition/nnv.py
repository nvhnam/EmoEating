"""Per-zone Nutritional Need Vector: macro gram targets + priority micro targets."""
from __future__ import annotations

from dataclasses import dataclass

from emoeating.config import (
    MEAL_FRACTION,
    MICRO_RDA,
    ZONE_MACRO_RATIOS,
    ZONE_PRIORITY_MICROS,
)
from emoeating.data.schema import Zone
from emoeating.nutrition.energy import Profile, per_meal_kcal

# kcal per gram by macronutrient
_KCAL_PER_G = {"protein_g": 4.0, "carb_g": 4.0, "fat_g": 9.0}
_RATIO_KEY = {"protein_g": "protein", "carb_g": "carb", "fat_g": "fat"}


@dataclass
class NutritionalNeedVector:
    zone: Zone
    macro_targets: dict[str, float]
    micro_targets: dict[str, float]
    priority_micros: list[str]


def build_nnv(zone: Zone, profile: Profile | None = None) -> NutritionalNeedVector:
    kcal = per_meal_kcal(profile)
    ratios = ZONE_MACRO_RATIOS[zone.value]
    macro_targets = {
        macro: kcal * ratios[_RATIO_KEY[macro]] / _KCAL_PER_G[macro]
        for macro in ("protein_g", "carb_g", "fat_g")
    }
    priority = ZONE_PRIORITY_MICROS[zone.value]
    micro_targets = {n: MICRO_RDA[n] * MEAL_FRACTION for n in priority}
    return NutritionalNeedVector(
        zone=zone,
        macro_targets=macro_targets,
        micro_targets=micro_targets,
        priority_micros=list(priority),
    )
