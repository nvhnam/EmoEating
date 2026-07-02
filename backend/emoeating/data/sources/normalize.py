"""Shared nutrient-unit normalization: map raw source fields/units -> canonical keys.

Every source parser funnels its raw numbers through here so that Food.nutrients
always uses the canonical keys and units that ENMS (subsystem 1) reads. This is
the single place unit conversions live (DRY).
"""
from __future__ import annotations

# Canonical micronutrient keys (macros live in schema.MACRO_KEYS).
CANONICAL_MICRO_KEYS: tuple[str, ...] = (
    "vit_c_mg", "vit_e_mg", "magnesium_mg", "vit_b6_mg",
    "folate_ug", "vit_b12_ug", "vit_d_ug", "omega3_g", "fiber_g",
)

# Canonical unit implied by each key's suffix.
CANONICAL_UNIT: dict[str, str] = {
    "protein_g": "g", "carb_g": "g", "fat_g": "g",
    "vit_c_mg": "mg", "vit_e_mg": "mg", "magnesium_mg": "mg", "vit_b6_mg": "mg",
    "folate_ug": "ug", "vit_b12_ug": "ug", "vit_d_ug": "ug",
    "omega3_g": "g", "fiber_g": "g",
}

# Mass units expressed in grams. Greek-mu and "mcg" spellings alias to micrograms.
_GRAMS_PER_UNIT: dict[str, float] = {
    "kg": 1e3, "g": 1.0, "mg": 1e-3,
    "ug": 1e-6, "µg": 1e-6, "μg": 1e-6, "mcg": 1e-6,
}


def convert(value: float, from_unit: str, to_unit: str) -> float:
    """Convert a mass `value` from one unit to another via grams (case-insensitive)."""
    from_normalized = from_unit.strip().lower()
    to_normalized = to_unit.strip().lower()

    if from_normalized not in _GRAMS_PER_UNIT:
        raise ValueError(f"Unknown unit: {from_normalized!r}")
    if to_normalized not in _GRAMS_PER_UNIT:
        raise ValueError(f"Unknown unit: {to_normalized!r}")

    f = _GRAMS_PER_UNIT[from_normalized]
    t = _GRAMS_PER_UNIT[to_normalized]
    return value * f / t


def normalize(key: str, value: float, unit: str) -> float:
    """Convert (value, unit) into the canonical unit implied by `key`."""
    if key not in CANONICAL_UNIT:
        raise ValueError(f"Unknown canonical nutrient key: {key!r}")
    return convert(value, unit, CANONICAL_UNIT[key])


def add_nutrient(nutrients: dict[str, float], key: str, value, unit: str) -> None:
    """Set nutrients[key] in canonical units.

    None / blank / non-numeric values are skipped so a missing nutrient stays
    absent from the dict (ENMS defaults absent values to 0.0). A real 0.0 is kept.
    """
    if value is None:
        return
    try:
        v = float(value)
    except (TypeError, ValueError):
        return
    nutrients[key] = normalize(key, v, unit)
