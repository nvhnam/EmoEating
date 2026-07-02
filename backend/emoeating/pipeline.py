"""End-to-end: emotion distribution + foods -> ranked, zone-conditioned meals."""
from __future__ import annotations

from dataclasses import dataclass

from emoeating.affect.mapping import to_valence_arousal
from emoeating.affect.zones import assign_zone
from emoeating.data.schema import Food, Zone
from emoeating.nutrition.energy import Profile
from emoeating.nutrition.enms import rank_foods
from emoeating.nutrition.nnv import NutritionalNeedVector, build_nnv


@dataclass
class Recommendation:
    food: Food
    score: float


@dataclass
class RecommendationResult:
    zone: Zone
    valence: float
    arousal: float
    nnv: NutritionalNeedVector
    recommendations: list[Recommendation]


def recommend(
    emotion_probs: dict[str, float],
    foods: list[Food],
    profile: Profile | None = None,
    top_n: int = 10,
) -> RecommendationResult:
    valence, arousal = to_valence_arousal(emotion_probs)
    zone = assign_zone(valence, arousal)
    nnv = build_nnv(zone, profile)
    ranked = rank_foods(foods, nnv)[:top_n]
    recs = [Recommendation(food=f, score=s) for f, s in ranked]
    return RecommendationResult(
        zone=zone, valence=valence, arousal=arousal, nnv=nnv, recommendations=recs
    )
