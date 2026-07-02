"""Turn a 9-class emotion distribution into a point on the valence/arousal plane.

Default strategy is dominant-class placement, matching the paper's prose. The
Strategy seam lets an expected-value (full-distribution) variant drop in later
without touching zones or the pipeline.
"""
from __future__ import annotations

from typing import Protocol

from emoeating.config import EMOTION_VA


class VAStrategy(Protocol):
    def to_va(self, probs: dict[str, float]) -> tuple[float, float]: ...


class DominantClassStrategy:
    """Place the single highest-probability emotion on the V/A plane."""

    def to_va(self, probs: dict[str, float]) -> tuple[float, float]:
        if not probs:
            raise ValueError("emotion probability distribution is empty")
        label = max(probs, key=probs.__getitem__)
        return EMOTION_VA[label]   # KeyError on unknown label is intentional


def to_valence_arousal(
    probs: dict[str, float], strategy: VAStrategy | None = None
) -> tuple[float, float]:
    return (strategy or DominantClassStrategy()).to_va(probs)
