"""Parse USDA FoodData Central records into canonical Food objects.

USDA is the authoritative micronutrient backbone: FDC food records carry the full
macro+micro panel with explicit unit names, which we map onto canonical keys. Both
the bulk-download JSON shape and the live search-API shape are accepted.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Iterator

from emoeating.data.schema import Food
from emoeating.data.sources.normalize import add_nutrient

# USDA FDC nutrient name -> canonical key.
USDA_NUTRIENT_MAP: dict[str, str] = {
    "Protein": "protein_g",
    "Carbohydrate, by difference": "carb_g",
    "Total lipid (fat)": "fat_g",
    "Fiber, total dietary": "fiber_g",
    "Vitamin C, total ascorbic acid": "vit_c_mg",
    "Vitamin E (alpha-tocopherol)": "vit_e_mg",
    "Magnesium, Mg": "magnesium_mg",
    "Vitamin B-6": "vit_b6_mg",
    "Folate, total": "folate_ug",
    "Vitamin B-12": "vit_b12_ug",
    "Vitamin D (D2 + D3)": "vit_d_ug",
    "PUFA 18:3 n-3 c,c,c (ALA)": "omega3_g",
}


def _maybe_float(raw) -> float | None:
    """Return float(raw), or None if raw is blank/non-numeric."""
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _extract(fn: dict) -> tuple[str, str, object]:
    """Return (name, unit, amount) from either FDC nutrient shape."""
    nutrient = fn.get("nutrient")
    if isinstance(nutrient, dict):  # bulk-download shape
        return nutrient.get("name", ""), nutrient.get("unitName", ""), fn.get("amount")
    return fn.get("nutrientName", ""), fn.get("unitName", ""), fn.get("value")  # search shape


def parse_usda(records: Iterable[dict]) -> Iterator[Food]:
    for rec in records:
        nutrients: dict[str, float] = {}
        calories: float | None = None
        for fn in rec.get("foodNutrients", []):
            name, unit, amount = _extract(fn)
            if name == "Energy" and unit.upper() == "KCAL":
                if amount is not None:
                    calories = _maybe_float(amount)
                continue
            key = USDA_NUTRIENT_MAP.get(name)
            if key is None:
                continue
            add_nutrient(nutrients, key, amount, unit)
        description = rec.get("description", "")
        yield Food(
            id=f"usda:{rec.get('fdcId', 'unknown')}",
            name=description,
            source="usda",
            calories=calories,
            nutrients=nutrients,
            image_hint=description or None,
        )


def load_usda(path: str) -> Iterator[Food]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        if "FoundationFoods" in data:
            records = data["FoundationFoods"]
        elif "SRLegacyFoods" in data:
            records = data["SRLegacyFoods"]
        elif "foods" in data:
            records = data["foods"]
        else:
            records = []
    else:
        records = []
    yield from parse_usda(records)
