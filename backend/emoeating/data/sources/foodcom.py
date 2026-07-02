"""Parse Food.com recipe CSV dumps (RAW_recipes-style) into canonical Foods.

Food.com packs macros as %-daily-value in a `nutrition` list and carries no
micronutrients, so recipe items are macro-only here; their micros are filled later
by USDA enrichment in the ETL step.
"""
from __future__ import annotations

import ast
import csv
from collections.abc import Iterable, Iterator

from emoeating.data.schema import Food

# FDA daily reference values (grams) used to turn Food.com %DV into grams.
_DV_GRAMS = {"fat_g": 78.0, "protein_g": 50.0, "carb_g": 275.0}

# Positions of macro %DV values within the packed `nutrition` list.
_PDV_INDEX = {"fat_g": 1, "protein_g": 4, "carb_g": 6}


def _parse_nutrition(raw: str) -> tuple[float | None, dict[str, float]]:
    # Fix 2: guard against blank/malformed nutrition string — treat as empty list
    try:
        values = ast.literal_eval(raw) if raw and raw.strip() else []
    except (ValueError, SyntaxError):
        values = []

    calories = float(values[0]) if values and values[0] is not None else None

    # Fix 1: skip macro if index out of range, value is None, or not float-convertible
    nutrients: dict[str, float] = {}
    for key, idx in _PDV_INDEX.items():
        if idx >= len(values):
            continue
        val = values[idx]
        if val is None:
            continue
        try:
            nutrients[key] = float(val) / 100.0 * _DV_GRAMS[key]
        except (TypeError, ValueError):
            continue

    return calories, nutrients


def parse_foodcom(rows: Iterable[dict]) -> Iterator[Food]:
    for row in rows:
        food_id = row.get("id")
        if not food_id:
            continue  # skip records with missing/blank required id field
        calories, nutrients = _parse_nutrition(row.get("nutrition", ""))
        name = (row.get("name") or "").strip()
        yield Food(
            id=f"foodcom:{food_id}",
            name=name,
            source="foodcom",
            calories=calories,
            nutrients=nutrients,
            image_hint=name or None,
        )


def load_foodcom(path: str) -> Iterator[Food]:
    # Fix 3: materialise inside the `with` block so the file is closed promptly
    # even if the caller stops iterating early.
    with open(path, newline="", encoding="utf-8") as fh:
        foods = list(parse_foodcom(csv.DictReader(fh)))
    yield from foods
