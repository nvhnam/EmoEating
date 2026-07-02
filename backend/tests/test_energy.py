import pytest
from emoeating.nutrition.energy import Profile, bmr, per_meal_kcal
from emoeating import config


def test_bmr_male_reference():
    # Mifflin-St Jeor: 10*80 + 6.25*180 - 5*30 + 5 = 1780
    p = Profile(age=30, sex="male", height_cm=180, weight_kg=80, activity="moderate")
    assert bmr(p) == pytest.approx(1780.0)


def test_bmr_female_reference():
    # 10*60 + 6.25*165 - 5*30 - 161 = 1320.25
    p = Profile(age=30, sex="female", height_cm=165, weight_kg=60, activity="light")
    assert bmr(p) == pytest.approx(1320.25)


def test_per_meal_kcal_uses_activity_and_meal_fraction():
    p = Profile(age=30, sex="male", height_cm=180, weight_kg=80, activity="moderate")
    expected = 1780.0 * config.ACTIVITY_FACTORS["moderate"] * config.MEAL_FRACTION
    assert per_meal_kcal(p) == pytest.approx(expected)


def test_per_meal_kcal_without_profile_is_default():
    assert per_meal_kcal(None) == config.DEFAULT_MEAL_KCAL


def test_bmr_rejects_invalid_sex():
    p = Profile(age=30, sex="Male", height_cm=180, weight_kg=80, activity="moderate")
    with pytest.raises(ValueError):
        bmr(p)


def test_per_meal_kcal_rejects_invalid_activity():
    p = Profile(age=30, sex="male", height_cm=180, weight_kg=80, activity="lazy")
    with pytest.raises(ValueError):
        per_meal_kcal(p)
