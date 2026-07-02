import pytest
from emoeating.nutrition.nnv import build_nnv, NutritionalNeedVector
from emoeating.nutrition.energy import Profile
from emoeating.data.schema import Zone
from emoeating import config


def test_macro_targets_from_default_kcal():
    nnv = build_nnv(Zone.POS_ACTIVE, None)
    kcal = config.DEFAULT_MEAL_KCAL
    r = config.ZONE_MACRO_RATIOS["POS_ACTIVE"]
    assert nnv.macro_targets["protein_g"] == pytest.approx(kcal * r["protein"] / 4)
    assert nnv.macro_targets["carb_g"] == pytest.approx(kcal * r["carb"] / 4)
    assert nnv.macro_targets["fat_g"] == pytest.approx(kcal * r["fat"] / 9)


def test_priority_micros_and_targets():
    nnv = build_nnv(Zone.NEG_DEACTIVE, None)
    assert nnv.priority_micros == config.ZONE_PRIORITY_MICROS["NEG_DEACTIVE"]
    assert nnv.micro_targets["omega3_g"] == pytest.approx(
        config.MICRO_RDA["omega3_g"] * config.MEAL_FRACTION
    )


def test_profile_scales_macro_targets():
    profile = Profile(age=30, sex="male", height_cm=180, weight_kg=80, activity="moderate")
    with_profile = build_nnv(Zone.POS_ACTIVE, profile)
    without = build_nnv(Zone.POS_ACTIVE, None)
    assert with_profile.macro_targets["carb_g"] != without.macro_targets["carb_g"]
