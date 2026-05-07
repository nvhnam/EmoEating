"""
BMI computation and energy need estimation.
Uses Mifflin-St Jeor equation (1990) — current clinical standard.

Mifflin, M. D., et al. (1990). A new predictive equation for resting energy expenditure.
American Journal of Clinical Nutrition, 51(2), 241–247.

Activity multiplier fixed at 1.2 (sedentary) for post-work home scenario.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PhysiologicalProfile:
    age: int
    sex: str                 # 'male' | 'female' | 'other'
    height_cm: float
    weight_kg: float
    bmi: float
    bmi_category: str        # 'underweight' | 'normal' | 'overweight' | 'obese'
    bmr_kcal: float
    tdee_kcal: float
    meal_kcal_target: float  # tdee / 3


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
        Other:  average of male and female formulas
    """
    base = 10.0 * weight_kg + 6.25 * height_cm - 5.0 * age
    if sex == "male":
        return base + 5.0
    elif sex == "female":
        return base - 161.0
    else:
        return base - 78.0  # midpoint of male (+5) and female (-161)


def compute_profile(
    age: int,
    sex: str,
    height_cm: float,
    weight_kg: float,
    activity_multiplier: float = 1.2,
    meals_per_day: int = 3,
) -> PhysiologicalProfile:
    """
    Compute full physiological profile.

    BMI = weight_kg / (height_m)²
    TDEE = BMR × activity_multiplier (default 1.2 = sedentary)
    meal_kcal_target = TDEE / meals_per_day
    """
    height_m = height_cm / 100.0
    bmi = weight_kg / (height_m ** 2)
    category = _bmi_category(bmi)
    bmr = _mifflin_bmr(weight_kg, height_cm, age, sex.lower())
    tdee = bmr * activity_multiplier
    meal_target = tdee / meals_per_day

    return PhysiologicalProfile(
        age=age,
        sex=sex.lower(),
        height_cm=height_cm,
        weight_kg=weight_kg,
        bmi=round(bmi, 1),
        bmi_category=category,
        bmr_kcal=round(bmr, 1),
        tdee_kcal=round(tdee, 1),
        meal_kcal_target=round(meal_target, 1),
    )


def profile_to_dict(profile: PhysiologicalProfile) -> dict:
    """Serialize PhysiologicalProfile to dict for DB storage/session state."""
    return {
        "age":               profile.age,
        "sex":               profile.sex,
        "height_cm":         profile.height_cm,
        "weight_kg":         profile.weight_kg,
        "bmi":               profile.bmi,
        "bmi_category":      profile.bmi_category,
        "bmr_kcal":          profile.bmr_kcal,
        "tdee_kcal":         profile.tdee_kcal,
        "meal_kcal_target":  profile.meal_kcal_target,
    }
