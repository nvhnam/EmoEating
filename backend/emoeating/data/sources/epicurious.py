"""Parse Epicurious recipe CSV (epi_r-style) into canonical Foods.

Epicurious carries calories plus protein/fat in grams (no carbs, no micros); like
Food.com, its items rely on USDA enrichment to fill the micronutrient panel.
"""
from __future__ import annotations

import csv
from collections.abc import Iterable, Iterator

from emoeating.data.schema import Food
from emoeating.data.sources.normalize import add_nutrient


def _maybe_float(raw) -> float | None:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def parse_epicurious(rows: Iterable[dict]) -> Iterator[Food]:
    for index, row in enumerate(rows):
        nutrients: dict[str, float] = {}
        add_nutrient(nutrients, "protein_g", row.get("protein"), "g")
        add_nutrient(nutrients, "fat_g", row.get("fat"), "g")
        name = (row.get("title") or "").strip()
        yield Food(
            id=f"epicurious:{index}",
            name=name,
            source="epicurious",
            calories=_maybe_float(row.get("calories")),
            nutrients=nutrients,
            image_hint=name or None,
        )


def load_epicurious(path: str) -> Iterator[Food]:
    with open(path, newline="", encoding="utf-8") as fh:
        yield from parse_epicurious(csv.DictReader(fh))
