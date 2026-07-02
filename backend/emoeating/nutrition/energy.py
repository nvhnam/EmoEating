"""Resting energy (Mifflin-St Jeor) and per-meal kcal target."""
from __future__ import annotations

from dataclasses import dataclass

from emoeating.config import ACTIVITY_FACTORS, DEFAULT_MEAL_KCAL, MEAL_FRACTION


@dataclass
class Profile:
    age: int
    sex: str           # "male" or "female"
    height_cm: float
    weight_kg: float
    activity: str      # key into ACTIVITY_FACTORS


def bmr(profile: Profile) -> float:
    if profile.sex not in ("male", "female"):
        raise ValueError(f"sex must be 'male' or 'female', got {profile.sex!r}")
    base = 10.0 * profile.weight_kg + 6.25 * profile.height_cm - 5.0 * profile.age
    return base + (5.0 if profile.sex == "male" else -161.0)


def per_meal_kcal(profile: Profile | None) -> float:
    if profile is None:
        return DEFAULT_MEAL_KCAL
    if profile.activity not in ACTIVITY_FACTORS:
        raise ValueError(f"activity must be one of {sorted(ACTIVITY_FACTORS)}, got {profile.activity!r}")
    factor = ACTIVITY_FACTORS[profile.activity]
    return bmr(profile) * factor * MEAL_FRACTION
