import json
import pytest
from emoeating.data.sources.openfoodfacts import (
    parse_openfoodfacts,
    load_openfoodfacts,
)

_RECORDS = [
    {
        "code": "3017620422003",
        "product_name": "Orange Juice ",
        "nutriments": {
            "energy-kcal_100g": 45.0,
            "proteins_100g": 0.7,
            "carbohydrates_100g": 10.4,
            "fat_100g": 0.2,
            "vitamin-c_100g": 0.05,     # grams -> 50 mg
            "vitamin-b9_100g": 0.0003,  # grams -> 300 ug folate
        },
    }
]


def test_parse_converts_per_100g_grams_to_canonical_units():
    food = next(parse_openfoodfacts(_RECORDS))
    assert food.id == "off:3017620422003"
    assert food.source == "openfoodfacts"
    assert food.name == "Orange Juice"           # trimmed
    assert food.calories == pytest.approx(45.0)
    assert food.amount("protein_g") == pytest.approx(0.7)
    assert food.amount("carb_g") == pytest.approx(10.4)
    assert food.amount("fat_g") == pytest.approx(0.2)         # fat_100g: 0.2
    assert food.amount("vit_c_mg") == pytest.approx(50.0)     # 0.05 g -> 50 mg
    assert food.amount("folate_ug") == pytest.approx(300.0)   # 0.0003 g -> 300 ug
    assert "vit_d_ug" not in food.nutrients                    # absent stays absent


def test_load_openfoodfacts_reads_json_file(tmp_path):
    path = tmp_path / "off.json"
    path.write_text(json.dumps({"products": _RECORDS}), encoding="utf-8")
    foods = list(load_openfoodfacts(str(path)))
    assert len(foods) == 1 and foods[0].id == "off:3017620422003"


def test_parse_missing_nutriments_yields_food_no_crash():
    records = [{"code": "0000000000000", "product_name": "Empty"}]
    food = next(parse_openfoodfacts(records))
    assert food.id == "off:0000000000000"
    assert food.nutrients == {}
    assert food.calories is None


def test_load_openfoodfacts_reads_bare_list_json(tmp_path):
    path = tmp_path / "off_bare_list.json"
    path.write_text(json.dumps(_RECORDS), encoding="utf-8")
    foods = list(load_openfoodfacts(str(path)))
    assert len(foods) == 1 and foods[0].id == "off:3017620422003"


# ---------------------------------------------------------------------------
# Fix 1 — tolerant calorie parsing
# ---------------------------------------------------------------------------

def test_blank_energy_kcal_yields_calories_none():
    """Blank energy-kcal_100g must not raise; calories should be None."""
    records = [{"code": "1111111111111", "product_name": "Blank Cal", "nutriments": {"energy-kcal_100g": ""}}]
    food = next(parse_openfoodfacts(records))
    assert food.calories is None


# ---------------------------------------------------------------------------
# Fix 2 — missing 'code' field causes record to be skipped
# ---------------------------------------------------------------------------

def test_record_missing_code_is_skipped():
    """A product dict without a 'code' key must be silently skipped."""
    records = [
        {"product_name": "No Code Product", "nutriments": {}},        # no code -> skip
        {"code": "9999999999999", "product_name": "Has Code", "nutriments": {}},  # valid
    ]
    foods = list(parse_openfoodfacts(records))
    assert len(foods) == 1
    assert foods[0].id == "off:9999999999999"
