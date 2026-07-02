import pytest
from emoeating.data.sources.foodcom import parse_foodcom, load_foodcom

_ROWS = [
    {
        "id": "38",
        "name": "lentil soup",
        # [calories, fat%DV, sugar%DV, sodium%DV, protein%DV, sat-fat%DV, carb%DV]
        "nutrition": "[300.0, 10.0, 5.0, 8.0, 20.0, 4.0, 12.0]",
    }
]

_CSV = """id,name,nutrition
38,lentil soup,"[300.0, 10.0, 5.0, 8.0, 20.0, 4.0, 12.0]"
"""


def test_parse_converts_pdv_macros_to_grams():
    food = next(parse_foodcom(_ROWS))
    assert food.id == "foodcom:38"
    assert food.source == "foodcom"
    assert food.calories == pytest.approx(300.0)
    assert food.amount("fat_g") == pytest.approx(10.0 / 100.0 * 78.0)       # 7.8
    assert food.amount("protein_g") == pytest.approx(20.0 / 100.0 * 50.0)   # 10.0
    assert food.amount("carb_g") == pytest.approx(12.0 / 100.0 * 275.0)     # 33.0


def test_foodcom_has_no_micros():
    food = next(parse_foodcom(_ROWS))
    assert food.amount("omega3_g") == 0.0   # absent; enrichment fills it later
    assert "vit_c_mg" not in food.nutrients


def test_load_foodcom_reads_csv_file(tmp_path):
    path = tmp_path / "recipes.csv"
    path.write_text(_CSV, encoding="utf-8")
    foods = list(load_foodcom(str(path)))
    assert len(foods) == 1 and foods[0].name == "lentil soup"


def test_none_macro_position_is_omitted():
    """A None in the fat_g slot omits that key but keeps protein_g and carb_g."""
    row = {
        "id": "99",
        "name": "partial food",
        "nutrition": "[300.0, None, 5.0, 8.0, 20.0, 4.0, 12.0]",
    }
    food = next(parse_foodcom([row]))
    assert "fat_g" not in food.nutrients
    assert food.amount("protein_g") == pytest.approx(20.0 / 100.0 * 50.0)
    assert food.amount("carb_g") == pytest.approx(12.0 / 100.0 * 275.0)
    assert food.calories == pytest.approx(300.0)


def test_blank_nutrition_yields_food_with_empty_nutrients():
    """A blank nutrition cell still yields a Food — just with no nutrients."""
    row = {"id": "100", "name": "blank food", "nutrition": ""}
    food = next(parse_foodcom([row]))
    assert food.id == "foodcom:100"
    assert food.nutrients == {}
    assert food.calories is None


def test_malformed_nutrition_yields_food_without_crash():
    """A malformed nutrition string still yields a Food — no exception raised."""
    row = {"id": "101", "name": "bad food", "nutrition": "[1,2,"}
    food = next(parse_foodcom([row]))
    assert food.id == "foodcom:101"
    assert food.nutrients == {}
    assert food.calories is None


# ---------------------------------------------------------------------------
# Fix 2 — missing required fields
# ---------------------------------------------------------------------------

def test_row_missing_id_is_skipped():
    """A row without an 'id' key must be silently skipped."""
    rows = [
        {"name": "no id food", "nutrition": "[300.0, 10.0, 5.0, 8.0, 20.0, 4.0, 12.0]"},  # no id -> skip
        {"id": "200", "name": "has id", "nutrition": "[100.0]"},  # valid
    ]
    foods = list(parse_foodcom(rows))
    assert len(foods) == 1
    assert foods[0].id == "foodcom:200"


def test_row_missing_nutrition_yields_food_with_empty_nutrients():
    """A row without a 'nutrition' key must still yield a Food with no nutrients."""
    row = {"id": "300", "name": "no nutrition col"}
    food = next(parse_foodcom([row]))
    assert food.id == "foodcom:300"
    assert food.nutrients == {}
    assert food.calories is None
