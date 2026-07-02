import pytest
from emoeating.data.sources.normalize import (
    CANONICAL_MICRO_KEYS,
    CANONICAL_UNIT,
    add_nutrient,
    convert,
    normalize,
)


def test_canonical_micro_keys_are_exact():
    assert CANONICAL_MICRO_KEYS == (
        "vit_c_mg", "vit_e_mg", "magnesium_mg", "vit_b6_mg",
        "folate_ug", "vit_b12_ug", "vit_d_ug", "omega3_g", "fiber_g",
    )


def test_convert_between_mass_units():
    assert convert(1.0, "g", "mg") == pytest.approx(1000.0)
    assert convert(500.0, "mg", "g") == pytest.approx(0.5)
    assert convert(400.0, "ug", "ug") == pytest.approx(400.0)
    assert convert(2.4, "UG", "ug") == pytest.approx(2.4)  # case-insensitive


def test_normalize_grams_to_key_unit():
    # 0.053 g of vitamin C -> 53 mg in the vit_c_mg canonical unit
    assert normalize("vit_c_mg", 0.053, "g") == pytest.approx(53.0)
    # 0.0004 g of folate -> 400 ug
    assert normalize("folate_ug", 0.0004, "g") == pytest.approx(400.0)


def test_add_nutrient_sets_canonical_value():
    n: dict[str, float] = {}
    add_nutrient(n, "vit_c_mg", 0.053, "g")
    assert n == {"vit_c_mg": pytest.approx(53.0)}


def test_add_nutrient_keeps_missing_absent():
    n: dict[str, float] = {}
    add_nutrient(n, "protein_g", None, "g")
    add_nutrient(n, "fat_g", "", "g")
    add_nutrient(n, "carb_g", "n/a", "g")
    assert n == {}  # no placeholders for absent values


def test_add_nutrient_keeps_real_zero():
    n: dict[str, float] = {}
    add_nutrient(n, "fiber_g", 0.0, "g")
    assert n == {"fiber_g": 0.0}


def test_canonical_unit_table_complete():
    """Assert all 12 canonical units are defined correctly."""
    expected = {
        "protein_g": "g", "carb_g": "g", "fat_g": "g",
        "vit_c_mg": "mg", "vit_e_mg": "mg", "magnesium_mg": "mg", "vit_b6_mg": "mg",
        "folate_ug": "ug", "vit_b12_ug": "ug", "vit_d_ug": "ug",
        "omega3_g": "g", "fiber_g": "g",
    }
    assert CANONICAL_UNIT == expected


def test_convert_unknown_unit_raises_valueerror():
    """Test that convert raises ValueError for unknown units."""
    with pytest.raises(ValueError, match="Unknown unit"):
        convert(1.0, "unknown_unit", "g")

    with pytest.raises(ValueError, match="Unknown unit"):
        convert(1.0, "g", "unknown_unit")


def test_normalize_unknown_key_raises_valueerror():
    """Test that normalize raises ValueError for unknown canonical keys."""
    with pytest.raises(ValueError, match="Unknown canonical nutrient key"):
        normalize("unknown_key", 1.0, "g")
