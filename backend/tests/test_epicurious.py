import pytest
from emoeating.data.sources.epicurious import parse_epicurious, load_epicurious

_ROWS = [
    {"title": "Roast Chicken ", "calories": "405.0", "protein": "32.0", "fat": "28.0"},
    {"title": "Mystery Dish", "calories": "", "protein": "", "fat": ""},  # all blank
]

_CSV = """title,calories,protein,fat
Roast Chicken,405.0,32.0,28.0
Mystery Dish,,,
"""


def test_parse_reads_grams_and_calories():
    foods = list(parse_epicurious(_ROWS))
    chicken = foods[0]
    assert chicken.id == "epicurious:0"
    assert chicken.source == "epicurious"
    assert chicken.name == "Roast Chicken"          # trimmed
    assert chicken.calories == pytest.approx(405.0)
    assert chicken.amount("protein_g") == pytest.approx(32.0)
    assert chicken.amount("fat_g") == pytest.approx(28.0)
    assert "carb_g" not in chicken.nutrients         # Epicurious has no carbs


def test_blank_cells_stay_absent():
    foods = list(parse_epicurious(_ROWS))
    mystery = foods[1]
    assert mystery.id == "epicurious:1"
    assert mystery.calories is None
    assert mystery.nutrients == {}


def test_load_epicurious_reads_csv_file(tmp_path):
    path = tmp_path / "epi.csv"
    path.write_text(_CSV, encoding="utf-8")
    foods = list(load_epicurious(str(path)))
    assert [f.name for f in foods] == ["Roast Chicken", "Mystery Dish"]
