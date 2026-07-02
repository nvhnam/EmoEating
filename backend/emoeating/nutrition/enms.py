"""Emotion-Nutrition Matching Score (spec section 6.4) and food ranking."""
from __future__ import annotations

from emoeating.config import ALPHA, BETA, GAMMA
from emoeating.data.schema import Food, MACRO_KEYS
from emoeating.nutrition.nnv import NutritionalNeedVector


def _capped_ratio(amount: float, target: float) -> float:
    if target <= 0:
        return 0.0
    return min(amount / target, 1.0)


def macro_score(food: Food, nnv: NutritionalNeedVector) -> float:
    terms = [_capped_ratio(food.amount(k), nnv.macro_targets[k]) for k in MACRO_KEYS]
    return sum(terms) / len(MACRO_KEYS)


def micro_score(food: Food, nnv: NutritionalNeedVector) -> float:
    if not nnv.priority_micros:
        return 0.0
    terms = [
        _capped_ratio(food.amount(k), nnv.micro_targets[k])
        for k in nnv.priority_micros
    ]
    return sum(terms) / len(nnv.priority_micros)


def enms(food: Food, nnv: NutritionalNeedVector, s_pref: float = 0.5) -> float:
    return (
        ALPHA * macro_score(food, nnv)
        + BETA * micro_score(food, nnv)
        + GAMMA * s_pref
    )


def rank_foods(
    foods: list[Food], nnv: NutritionalNeedVector, s_pref: float = 0.5
) -> list[tuple[Food, float]]:
    scored = [(f, enms(f, nnv, s_pref)) for f in foods]
    scored.sort(key=lambda pair: pair[1], reverse=True)  # stable sort preserves ties
    return scored
