from emoeating.data.schema import Food, Zone, MACRO_KEYS


def test_zone_members():
    assert {z.value for z in Zone} == {
        "POS_ACTIVE", "NEG_ACTIVE", "NEG_DEACTIVE", "NEUTRAL_CALM"
    }


def test_macro_keys():
    assert MACRO_KEYS == ("protein_g", "carb_g", "fat_g")


def test_food_amount_defaults_missing_to_zero():
    f = Food(id="1", name="Oatmeal", source="usda",
             calories=150.0, nutrients={"carb_g": 27.0, "fiber_g": 4.0},
             image_hint=None)
    assert f.amount("carb_g") == 27.0
    assert f.amount("vit_c_mg") == 0.0   # missing -> 0.0
