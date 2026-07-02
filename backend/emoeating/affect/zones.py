"""Sort a valence/arousal point into one of four affective zones (spec Table 1)."""
from __future__ import annotations

from emoeating.config import THETA
from emoeating.data.schema import Zone


def assign_zone(valence: float, arousal: float) -> Zone:
    if valence > THETA and arousal > THETA:
        return Zone.POS_ACTIVE
    if valence < -THETA and arousal > THETA:
        return Zone.NEG_ACTIVE
    if valence < -THETA and arousal <= THETA:
        return Zone.NEG_DEACTIVE
    return Zone.NEUTRAL_CALM
