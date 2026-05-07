"""Unit tests for engine/food_scorer.py"""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import pytest
from engine.food_scorer import score_foods
from engine.need_vector import compute_need_vector, NeedVector


def _make_norm_cache():
    """Minimal normalization cache for testing."""
    return {
        "tryptophan_mg":   {"min": 0.0,  "max": 1000.0},
        "omega3_mg":       {"min": 0.0,  "max": 5000.0},
        "complex_carbs_g": {"min": 0.0,  "max": 200.0},
        "magnesium_mg":    {"min": 0.0,  "max": 500.0},
        "iron_mg":         {"min": 0.0,  "max": 50.0},
        "vitamin_b12_mcg": {"min": 0.0,  "max": 10.0},
        "folate_mcg":      {"min": 0.0,  "max": 800.0},
        "vitamin_c_mg":    {"min": 0.0,  "max": 300.0},
        "vitamin_e_mg":    {"min": 0.0,  "max": 50.0},
        "sugar_g":         {"min": 0.0,  "max": 100.0},
        "protein_g":       {"min": 0.0,  "max": 100.0},
        "fiber_g":         {"min": 0.0,  "max": 50.0},
        "calories_kcal":   {"min": 0.0,  "max": 1000.0},
    }


def _make_food(name: str, **nutrients) -> dict:
    base = {"id": 1, "name": name, "calories_kcal": 400}
    base.update(nutrients)
    return base


def test_score_returns_all_foods():
    """score_foods should return a list of same length as input."""
    norm = _make_norm_cache()
    nv = compute_need_vector(-0.8, 0.8)  # angry-like
    foods = [_make_food(f"food_{i}", protein_g=i * 5) for i in range(5)]
    result = score_foods(foods, nv, norm)
    assert len(result) == 5


def test_score_adds_affective_score_key():
    norm = _make_norm_cache()
    nv = compute_need_vector(0.0, 0.0)
    foods = [_make_food("test", protein_g=10)]
    result = score_foods(foods, nv, norm)
    assert "affective_score" in result[0]


def test_score_adds_top_contributors_key():
    norm = _make_norm_cache()
    nv = compute_need_vector(-0.8, 0.8)
    foods = [_make_food("rich", protein_g=50, magnesium_mg=200, tryptophan_mg=500)]
    result = score_foods(foods, nv, norm)
    assert "top_contributors" in result[0]
    assert isinstance(result[0]["top_contributors"], list)


def test_null_nutrients_score_as_zero():
    """Food with all NULL nutrients should have affective_score = 0 when fiber weight=0.5."""
    norm = _make_norm_cache()
    nv = NeedVector(
        tryptophan=0.0, omega3=0.0, complex_carbs=0.0, magnesium=0.0,
        iron=0.0, b_vitamins=0.0, antioxidants=0.0, protein=0.0,
        fiber=0.0, sugar_penalty=0.0,
    )
    foods = [_make_food("empty", protein_g=None, fiber_g=None)]
    result = score_foods(foods, nv, norm)
    assert result[0]["affective_score"] == 0.0


def test_higher_nutrients_score_higher():
    """Food with more tryptophan should score higher when tryptophan weight is high."""
    norm = _make_norm_cache()
    nv = NeedVector(
        tryptophan=1.0, omega3=0.0, complex_carbs=0.0, magnesium=0.0,
        iron=0.0, b_vitamins=0.0, antioxidants=0.0, protein=0.0,
        fiber=0.0, sugar_penalty=0.0,
    )
    low  = _make_food("low",  tryptophan_mg=100)
    high = _make_food("high", tryptophan_mg=800)
    result = score_foods([low, high], nv, norm)
    scores = {r["name"]: r["affective_score"] for r in result}
    assert scores["high"] > scores["low"]


def test_sugar_penalty_lowers_score():
    """High sugar food should score lower when sugar_penalty weight is high."""
    norm = _make_norm_cache()
    nv = NeedVector(
        tryptophan=0.0, omega3=0.0, complex_carbs=0.0, magnesium=0.0,
        iron=0.0, b_vitamins=0.0, antioxidants=0.0, protein=0.0,
        fiber=0.0, sugar_penalty=1.0,
    )
    low_sugar  = _make_food("low",  sugar_g=5)
    high_sugar = _make_food("high", sugar_g=80)
    result = score_foods([low_sugar, high_sugar], nv, norm)
    scores = {r["name"]: r["affective_score"] for r in result}
    assert scores["low"] > scores["high"]


def test_score_bounded():
    """Scores should be positive (or very slightly negative only from penalty)."""
    norm = _make_norm_cache()
    nv = compute_need_vector(-0.7, -0.5)  # sad-like
    foods = [
        _make_food(f"f{i}",
                   protein_g=i*10, tryptophan_mg=i*100,
                   fiber_g=i*3, sugar_g=i*5)
        for i in range(10)
    ]
    result = score_foods(foods, nv, norm)
    for food in result:
        assert food["affective_score"] >= -1.0  # bounded from below by sugar penalty
