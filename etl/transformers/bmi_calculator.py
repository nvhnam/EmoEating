"""
Mifflin-St Jeor BMI/BMR/TDEE utilities for ETL use.
Mirrors app/engine/physiological.py but kept separate for ETL independence.
"""

from __future__ import annotations

def compute_bmi(weight_kg: float, height_cm: float) -> float:
    h = height_cm / 100.0
    return round(weight_kg / (h ** 2), 1)


def bmi_category(bmi: float) -> str:
    if bmi < 18.5:
        return "underweight"
    elif bmi < 25.0:
        return "normal"
    elif bmi < 30.0:
        return "overweight"
    else:
        return "obese"


def mifflin_bmr(weight_kg: float, height_cm: float, age: int, sex: str) -> float:
    base = 10.0 * weight_kg + 6.25 * height_cm - 5.0 * age
    if sex == "male":
        return round(base + 5.0, 1)
    elif sex == "female":
        return round(base - 161.0, 1)
    else:
        return round(base - 78.0, 1)
