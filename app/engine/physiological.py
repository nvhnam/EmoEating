"""
BMI computation and energy need estimation.
Uses Mifflin-St Jeor equation (1990) — current clinical standard.

Mifflin, M. D., et al. (1990). A new predictive equation for resting energy expenditure.
American Journal of Clinical Nutrition, 51(2), 241–247.

Activity levels and per-meal energy fractions per USDA Dietary Guidelines 2020–2025.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PhysiologicalProfile:
    age: int
    sex: str            # 'male' | 'female' | 'other'
    height_cm: float
    weight_kg: float
    bmi: float
    bmi_category: str   # 'underweight' | 'normal' | 'overweight' | 'obese'
    bmr_kcal: float
    tdee_kcal: float
    activity_level: str  # 'sedentary' | 'lightly_active' | 'moderately_active'


def _bmi_category(bmi: float) -> str:
    """WHO (2000) BMI classification."""
    if bmi < 18.5:
        return "underweight"
    elif bmi < 25.0:
        return "normal"
    elif bmi < 30.0:
        return "overweight"
    else:
        return "obese"


def _mifflin_bmr(weight_kg: float, height_cm: float, age: int, sex: str) -> float:
    """
    Mifflin-St Jeor BMR (kcal/day):
        Male:   10·w + 6.25·h − 5·a + 5
        Female: 10·w + 6.25·h − 5·a − 161
        Other:  midpoint of male and female
    """
    base = 10.0 * weight_kg + 6.25 * height_cm - 5.0 * age
    if sex == "male":
        return base + 5.0
    elif sex == "female":
        return base - 161.0
    else:
        return base - 78.0  # midpoint: (+5 + -161) / 2 = -78


def compute_profile(
    age: int,
    sex: str,
    height_cm: float,
    weight_kg: float,
    activity_level: str = "sedentary",
) -> PhysiologicalProfile:
    """
    Compute full physiological profile.

    BMI  = weight_kg / (height_m)²
    TDEE = BMR × ACTIVITY_MULTIPLIERS[activity_level]
    Per-meal energy: use meal_energy_target(tdee_kcal, meal_type) separately.
    """
    from config import ACTIVITY_MULTIPLIERS
    height_m = height_cm / 100.0
    bmi = weight_kg / (height_m ** 2)
    category = _bmi_category(bmi)
    bmr = _mifflin_bmr(weight_kg, height_cm, age, sex.lower())
    multiplier = ACTIVITY_MULTIPLIERS.get(activity_level, 1.2)
    tdee = bmr * multiplier

    return PhysiologicalProfile(
        age=age,
        sex=sex.lower(),
        height_cm=height_cm,
        weight_kg=weight_kg,
        bmi=round(bmi, 1),
        bmi_category=category,
        bmr_kcal=round(bmr, 1),
        tdee_kcal=round(tdee, 1),
        activity_level=activity_level,
    )


def meal_energy_target(tdee_kcal: float, meal_type: str) -> float:
    """
    Return per-meal energy target = TDEE × MEAL_ENERGY_FRACTION[meal_type].
    Fallback fraction 1/3 if meal_type not recognized.

    Proportions: breakfast 25%, lunch 35%, dinner 30%, snack 10%.
    Source: USDA Dietary Guidelines for Americans 2020–2025.
    """
    from config import MEAL_ENERGY_FRACTION
    fraction = MEAL_ENERGY_FRACTION.get(meal_type.lower(), 1 / 3)
    return round(tdee_kcal * fraction, 1)


def profile_to_dict(profile: PhysiologicalProfile) -> dict:
    """Serialize PhysiologicalProfile to dict for DB storage/session state."""
    return {
        "age":            profile.age,
        "sex":            profile.sex,
        "height_cm":      profile.height_cm,
        "weight_kg":      profile.weight_kg,
        "bmi":            profile.bmi,
        "bmi_category":   profile.bmi_category,
        "bmr_kcal":       profile.bmr_kcal,
        "tdee_kcal":      profile.tdee_kcal,
        "activity_level": profile.activity_level,
    }


def profile_from_dict(d: dict) -> PhysiologicalProfile:
    """Reconstruct PhysiologicalProfile from a serialized dict."""
    return PhysiologicalProfile(
        age=d["age"],
        sex=d["sex"],
        height_cm=d["height_cm"],
        weight_kg=d["weight_kg"],
        bmi=d["bmi"],
        bmi_category=d["bmi_category"],
        bmr_kcal=d["bmr_kcal"],
        tdee_kcal=d["tdee_kcal"],
        activity_level=d.get("activity_level", "sedentary"),
    )
