"""Unit tests for engine/physiological.py"""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import pytest
from engine.physiological import compute_profile, PhysiologicalProfile


def test_bmi_normal():
    """70kg, 175cm â†’ BMI â‰ˆ 22.9 (normal)."""
    p = compute_profile(30, "male", 175, 70)
    assert 22.0 <= p.bmi <= 24.0, f"BMI={p.bmi}"
    assert p.bmi_category == "normal"


def test_bmi_overweight():
    """90kg, 175cm â†’ BMI â‰ˆ 29.4 (overweight)."""
    p = compute_profile(30, "male", 175, 90)
    assert p.bmi_category == "overweight"


def test_bmi_underweight():
    """45kg, 175cm â†’ BMI < 18.5 (underweight)."""
    p = compute_profile(25, "female", 175, 45)
    assert p.bmi_category == "underweight"


def test_bmi_obese():
    """120kg, 170cm â†’ BMI â‰ˆ 41.5 (obese)."""
    p = compute_profile(40, "male", 170, 120)
    assert p.bmi_category == "obese"


def test_mifflin_male():
    """
    Male, 30y, 175cm, 70kg:
    BMR = 10*70 + 6.25*175 âˆ’ 5*30 + 5 = 700+1093.75âˆ’150+5 = 1648.75
    """
    p = compute_profile(30, "male", 175, 70)
    assert abs(p.bmr_kcal - 1648.75) < 1.0, f"BMR={p.bmr_kcal}"


def test_mifflin_female():
    """
    Female, 30y, 165cm, 60kg:
    BMR = 10*60 + 6.25*165 âˆ’ 5*30 âˆ’ 161 = 600+1031.25âˆ’150âˆ’161 = 1320.25
    """
    p = compute_profile(30, "female", 165, 60)
    assert abs(p.bmr_kcal - 1320.25) < 1.0, f"BMR={p.bmr_kcal}"


def test_tdee_sedentary():
    """TDEE = BMR Ã— 1.2."""
    p = compute_profile(30, "male", 175, 70)
    assert abs(p.tdee_kcal - p.bmr_kcal * 1.2) < 1.0


def test_meal_target_is_tdee_thirds():
    """Meal target = TDEE / 3."""
    p = compute_profile(30, "male", 175, 70)
    assert abs(p.meal_kcal_target - p.tdee_kcal / 3) < 1.0


def test_other_sex_is_average():
    """'other' sex uses average of male and female BMR."""
    pm = compute_profile(30, "male",   170, 70)
    pf = compute_profile(30, "female", 170, 70)
    po = compute_profile(30, "other",  170, 70)
    avg = (pm.bmr_kcal + pf.bmr_kcal) / 2
    assert abs(po.bmr_kcal - avg) < 1.0, f"other BMR={po.bmr_kcal}, avg={avg}"


def test_profile_fields_complete():
    """All PhysiologicalProfile fields must be populated."""
    p = compute_profile(25, "female", 160, 55)
    assert p.bmi > 0
    assert p.bmi_category in ("underweight", "normal", "overweight", "obese")
    assert p.bmr_kcal > 0
    assert p.tdee_kcal > 0
    assert p.meal_kcal_target > 0
