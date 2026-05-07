"""
Parses Food.com nutrition list strings (PDV format) to actual gram values.

Food.com nutrition column is a Python list string:
    [calories, total_fat%, sugar%, sodium%, protein%, sat_fat%, carbohydrates%]
    First element (calories) is kcal; rest are PDV (percent daily value).

FDA Daily Values used for conversion:
    protein      = 50g
    fat          = 78g
    carbohydrate = 275g
    saturated_fat = 20g
    sodium       = 2300mg (stored as mg in our schema)
    sugar        = 50g
"""

from __future__ import annotations

import ast
import re


FDA_DV = {
    "fat":          78.0,
    "sugar":        50.0,
    "sodium":       2300.0,   # mg
    "protein":      50.0,
    "sat_fat":      20.0,
    "carbohydrate": 275.0,
}


def parse_foodcom_nutrition(nutrition_str: str) -> dict:
    """
    Parse Food.com nutrition list string â†’ dict of nutrient values.
    Returns dict with keys: calories_kcal, fat_g, sugar_g, sodium_mg,
                            protein_g, saturated_fat_g, carbohydrate_g.
    Returns empty dict on parse failure.
    """
    try:
        vals = ast.literal_eval(str(nutrition_str))
        if not isinstance(vals, list) or len(vals) < 7:
            return {}
        kcal, fat_pdv, sugar_pdv, sodium_pdv, prot_pdv, satfat_pdv, carb_pdv = vals[:7]

        return {
            "calories_kcal":    float(kcal),
            "fat_g":            _pdv_to_g(fat_pdv,    FDA_DV["fat"]),
            "sugar_g":          _pdv_to_g(sugar_pdv,  FDA_DV["sugar"]),
            "sodium_mg":        _pdv_to_g(sodium_pdv, FDA_DV["sodium"]),
            "protein_g":        _pdv_to_g(prot_pdv,   FDA_DV["protein"]),
            "saturated_fat_g":  _pdv_to_g(satfat_pdv, FDA_DV["sat_fat"]),
            "carbohydrate_g":   _pdv_to_g(carb_pdv,   FDA_DV["carbohydrate"]),
        }
    except Exception:
        return {}


def _pdv_to_g(pdv_pct, dv_g: float) -> float:
    """Convert percent daily value to grams."""
    return round(float(pdv_pct) / 100.0 * dv_g, 3)


def parse_list_column(raw: str) -> list[str]:
    """Parse a Python list string from a CSV column into a Python list."""
    try:
        result = ast.literal_eval(str(raw))
        return [str(x) for x in result] if isinstance(result, list) else []
    except Exception:
        return []


def estimate_tryptophan(protein_g: float | None) -> float | None:
    """
    Estimate tryptophan from protein content.
    Average Trp fraction in food protein: ~1.1% (FAO/WHO 2007).
    Returns mg.
    """
    if protein_g is None:
        return None
    return round(float(protein_g) * 0.011 * 1000, 3)  # g â†’ mg
