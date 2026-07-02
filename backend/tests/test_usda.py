import json
import pytest
from emoeating.data.sources.usda import parse_usda, load_usda

# Bulk-download shape: foodNutrients[].nutrient.{name,unitName}, amount.
_BULK = [
    {
        "fdcId": 173410,
        "description": "Salmon, Atlantic, cooked",
        "foodNutrients": [
            {"nutrient": {"name": "Energy", "unitName": "KCAL"}, "amount": 206.0},
            {"nutrient": {"name": "Protein", "unitName": "G"}, "amount": 22.1},
            {"nutrient": {"name": "Total lipid (fat)", "unitName": "G"}, "amount": 12.4},
            {"nutrient": {"name": "Magnesium, Mg", "unitName": "MG"}, "amount": 29.0},
            {"nutrient": {"name": "Vitamin B-12", "unitName": "UG"}, "amount": 2.8},
            {"nutrient": {"name": "PUFA 18:3 n-3 c,c,c (ALA)", "unitName": "G"}, "amount": 0.3},
            {"nutrient": {"name": "Caffeine", "unitName": "MG"}, "amount": 0.0},  # unmapped
        ],
    }
]

# Search-API shape: foodNutrients[].{nutrientName,unitName,value}.
_SEARCH = [
    {
        "fdcId": 169905,
        "description": "Orange, raw",
        "foodNutrients": [
            {"nutrientName": "Vitamin C, total ascorbic acid", "unitName": "MG", "value": 53.2},
            {"nutrientName": "Carbohydrate, by difference", "unitName": "G", "value": 11.8},
        ],
    }
]


def test_parse_bulk_maps_names_units_and_energy():
    food = next(parse_usda(_BULK))
    assert food.id == "usda:173410"
    assert food.source == "usda"
    assert food.calories == pytest.approx(206.0)
    assert food.amount("protein_g") == pytest.approx(22.1)
    assert food.amount("magnesium_mg") == pytest.approx(29.0)
    assert food.amount("vit_b12_ug") == pytest.approx(2.8)
    assert food.amount("omega3_g") == pytest.approx(0.3)
    assert "caffeine" not in food.nutrients          # unmapped nutrient dropped
    assert food.amount("vit_c_mg") == 0.0            # absent -> default 0.0


def test_parse_handles_search_api_shape():
    food = next(parse_usda(_SEARCH))
    assert food.amount("vit_c_mg") == pytest.approx(53.2)
    assert food.amount("carb_g") == pytest.approx(11.8)
    assert food.calories is None                     # no Energy row


def test_load_usda_reads_json_file(tmp_path):
    path = tmp_path / "fdc.json"
    path.write_text(json.dumps({"FoundationFoods": _BULK}), encoding="utf-8")
    foods = list(load_usda(str(path)))
    assert len(foods) == 1 and foods[0].id == "usda:173410"


def test_load_usda_handles_foundation_foods_shape(tmp_path):
    """Test dict with FoundationFoods key."""
    path = tmp_path / "foundation.json"
    path.write_text(json.dumps({"FoundationFoods": _BULK}), encoding="utf-8")
    foods = list(load_usda(str(path)))
    assert len(foods) == 1
    assert foods[0].id == "usda:173410"
    assert foods[0].amount("protein_g") == pytest.approx(22.1)


def test_load_usda_handles_sr_legacy_foods_shape(tmp_path):
    """Test dict with SRLegacyFoods key."""
    path = tmp_path / "sr_legacy.json"
    path.write_text(json.dumps({"SRLegacyFoods": _SEARCH}), encoding="utf-8")
    foods = list(load_usda(str(path)))
    assert len(foods) == 1
    assert foods[0].id == "usda:169905"
    assert foods[0].amount("vit_c_mg") == pytest.approx(53.2)


def test_load_usda_handles_foods_key_shape(tmp_path):
    """Test dict with 'foods' key (search API shape)."""
    path = tmp_path / "foods.json"
    path.write_text(json.dumps({"foods": _BULK}), encoding="utf-8")
    foods = list(load_usda(str(path)))
    assert len(foods) == 1
    assert foods[0].id == "usda:173410"
    assert foods[0].amount("protein_g") == pytest.approx(22.1)


def test_load_usda_handles_raw_list_shape(tmp_path):
    """Test raw top-level list of records."""
    path = tmp_path / "raw_list.json"
    path.write_text(json.dumps(_BULK), encoding="utf-8")
    foods = list(load_usda(str(path)))
    assert len(foods) == 1
    assert foods[0].id == "usda:173410"
    assert foods[0].amount("protein_g") == pytest.approx(22.1)


def test_load_usda_empty_foundation_foods_returns_no_foods(tmp_path):
    """Regression: empty FoundationFoods list should return no foods (not fall through to other keys)."""
    path = tmp_path / "empty_foundation.json"
    path.write_text(
        json.dumps({"FoundationFoods": [], "foods": _BULK}), encoding="utf-8"
    )
    foods = list(load_usda(str(path)))
    # Should use FoundationFoods (empty) and NOT fall through to "foods"
    assert len(foods) == 0


# ---------------------------------------------------------------------------
# Fix 1 — tolerant calorie parsing
# ---------------------------------------------------------------------------

def _energy_record(value) -> list[dict]:
    """Build a single-record USDA fixture with the given energy amount."""
    return [
        {
            "fdcId": 999,
            "description": "Test Food",
            "foodNutrients": [
                {"nutrient": {"name": "Energy", "unitName": "KCAL"}, "amount": value},
            ],
        }
    ]


def test_blank_energy_yields_food_with_calories_none():
    """Blank string energy value must not raise; calories should be None."""
    foods = list(parse_usda(_energy_record("")))
    assert len(foods) == 1
    assert foods[0].calories is None


def test_non_numeric_energy_yields_food_with_calories_none():
    """'n/a' energy value must not raise; calories should be None."""
    foods = list(parse_usda(_energy_record("n/a")))
    assert len(foods) == 1
    assert foods[0].calories is None
