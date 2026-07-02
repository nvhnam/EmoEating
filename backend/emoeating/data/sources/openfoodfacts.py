"""Parse Open Food Facts product records into canonical Foods.

OFF reports every nutriment per 100g in grams (including vitamins), so each field
is mapped to its canonical key and unit-converted (e.g. vitamin-c grams -> mg).
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Iterator

from emoeating.data.schema import Food
from emoeating.data.sources.normalize import add_nutrient


def _maybe_float(raw) -> float | None:
    """Return float(raw), or None if raw is blank/non-numeric."""
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None

# OFF nutriment field (per 100g, grams) -> canonical key.
OFF_NUTRIENT_MAP: dict[str, str] = {
    "proteins_100g": "protein_g",
    "carbohydrates_100g": "carb_g",
    "fat_100g": "fat_g",
    "fiber_100g": "fiber_g",
    "vitamin-c_100g": "vit_c_mg",
    "vitamin-e_100g": "vit_e_mg",
    "magnesium_100g": "magnesium_mg",
    "vitamin-b6_100g": "vit_b6_mg",
    "vitamin-b9_100g": "folate_ug",
    "vitamin-b12_100g": "vit_b12_ug",
    "vitamin-d_100g": "vit_d_ug",
    "omega-3-fat_100g": "omega3_g",
}


def parse_openfoodfacts(records: Iterable[dict]) -> Iterator[Food]:
    for rec in records:
        code = rec.get("code")
        if not code:
            continue  # skip records with missing/blank required id field
        nutriments = rec.get("nutriments", {})
        nutrients: dict[str, float] = {}
        for field, key in OFF_NUTRIENT_MAP.items():
            if field in nutriments:
                add_nutrient(nutrients, key, nutriments[field], "g")
        calories = nutriments.get("energy-kcal_100g")
        name = (rec.get("product_name") or "").strip()
        yield Food(
            id=f"off:{code}",
            name=name,
            source="openfoodfacts",
            calories=_maybe_float(calories),
            nutrients=nutrients,
            image_hint=name or None,
        )


def load_openfoodfacts(path: str) -> Iterator[Food]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    records = data.get("products", []) if isinstance(data, dict) else data
    yield from parse_openfoodfacts(records)
