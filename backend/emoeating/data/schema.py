"""Unified food record and the canonical vocabulary shared across the package."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Zone(str, Enum):
    POS_ACTIVE = "POS_ACTIVE"
    NEG_ACTIVE = "NEG_ACTIVE"
    NEG_DEACTIVE = "NEG_DEACTIVE"
    NEUTRAL_CALM = "NEUTRAL_CALM"


# The three macronutrients ENMS scores, as keys into Food.nutrients.
MACRO_KEYS: tuple[str, str, str] = ("protein_g", "carb_g", "fat_g")


@dataclass
class Food:
    id: str
    name: str
    source: str
    calories: float | None
    nutrients: dict[str, float] = field(default_factory=dict)
    image_hint: str | None = None

    def amount(self, key: str) -> float:
        """Nutrient amount in canonical units; missing values default to 0.0."""
        return self.nutrients.get(key, 0.0)
