import pytest
from emoeating.nutrition.enms import macro_score, micro_score, enms, rank_foods, _capped_ratio
from emoeating.nutrition.nnv import build_nnv, NutritionalNeedVector
from emoeating.data.schema import Food, Zone
from emoeating import config


def _food(**nutrients):
    return Food(id="x", name="x", source="t", calories=None, nutrients=nutrients)


def test_macro_score_caps_at_one():
    nnv = build_nnv(Zone.POS_ACTIVE, None)
    huge = _food(protein_g=1e6, carb_g=1e6, fat_g=1e6)
    assert macro_score(huge, nnv) == pytest.approx(1.0)


def test_macro_score_missing_macro_scores_zero_term():
    nnv = build_nnv(Zone.POS_ACTIVE, None)
    # only carbs supplied -> two of three macro terms are 0
    f = _food(carb_g=nnv.macro_targets["carb_g"])
    assert macro_score(f, nnv) == pytest.approx(1.0 / 3.0)


def test_micro_score_empty_priority_is_zero_safe():
    # NEUTRAL_CALM has 2 micros; supply none -> 0.0, no division error
    nnv = build_nnv(Zone.NEUTRAL_CALM, None)
    assert micro_score(_food(), nnv) == 0.0


def test_enms_combines_weighted_terms_with_pref_prior():
    nnv = build_nnv(Zone.POS_ACTIVE, None)
    f = _food(carb_g=nnv.macro_targets["carb_g"])  # macro=1/3, micro=0
    expected = config.ALPHA * (1.0 / 3.0) + config.BETA * 0.0 + config.GAMMA * 0.5
    assert enms(f, nnv) == pytest.approx(expected)


def test_rank_orders_descending():
    nnv = build_nnv(Zone.POS_ACTIVE, None)
    good = Food(id="good", name="good", source="t", calories=None,
                nutrients=dict(protein_g=nnv.macro_targets["protein_g"],
                               carb_g=nnv.macro_targets["carb_g"],
                               fat_g=nnv.macro_targets["fat_g"],
                               vit_c_mg=1e3, vit_e_mg=1e3))
    poor = Food(id="poor", name="poor", source="t", calories=None, nutrients={})
    ranked = rank_foods([poor, good], nnv)
    assert [f.id for f, _ in ranked] == ["good", "poor"]
    assert ranked[0][1] > ranked[1][1]
    assert ranked[0][0] is good


def test_micro_score_truly_empty_priority_list():
    """Test that micro_score returns 0.0 when priority_micros is truly empty."""
    nnv = NutritionalNeedVector(zone=Zone.NEUTRAL_CALM, macro_targets={},
                                micro_targets={}, priority_micros=[])
    assert micro_score(_food(), nnv) == 0.0


def test_capped_ratio_target_zero_is_zero():
    """Test that _capped_ratio returns 0.0 for zero and negative targets."""
    assert _capped_ratio(5.0, 0.0) == 0.0
    assert _capped_ratio(5.0, -1.0) == 0.0


def test_rank_foods_tie_stability():
    """Test that rank_foods preserves input order for foods with identical scores."""
    nnv = build_nnv(Zone.POS_ACTIVE, None)
    # Create two foods with identical nutrients (same score)
    food_first = Food(id="first", name="x", source="t", calories=None, nutrients={})
    food_second = Food(id="second", name="x", source="t", calories=None, nutrients={})

    ranked = rank_foods([food_first, food_second], nnv)
    ranked_ids = [f.id for f, _ in ranked]
    assert ranked_ids == ["first", "second"], "Tie should preserve input order"
