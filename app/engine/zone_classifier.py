"""
Stage 2: Classifies (Valence, Arousal) into emotional zones per Russell (1980) circumplex.

Russell, J. A. (1980). A circumplex model of affect.
Journal of Personality and Social Psychology, 39(6), 1161–1178.

Posner, J., Russell, J. A., & Peterson, B. S. (2005).
The circumplex model of affect: An integrative approach to affective neuroscience.
Development and Psychopathology, 17(3), 715–734. DOI:10.1017/S0954579405050340

Zone definitions:
  NEUTRAL    : ||(V, A)|| < THETA_NEUTRAL  (near origin)
  Q2_STRESSED: V < 0, A ≥ 0  (unpleasant + high arousal)
  Q3_FATIGUED: V < 0, A < 0  (unpleasant + low arousal)
  Q1_HAPPY   : V > 0, A ≥ 0  (pleasant + high arousal)
  Q4_CONTENT : V > 0, A < 0  (pleasant + low arousal)

THETA_NEUTRAL = 0.25 is a design parameter documented in the paper.
"""

from __future__ import annotations

import math
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import THETA_NEUTRAL


def classify_zone(V: float, A: float) -> str:
    """
    Map (Valence, Arousal) to one of five emotional zones.

    Returns one of: 'NEUTRAL', 'Q1_HAPPY', 'Q2_STRESSED', 'Q3_FATIGUED', 'Q4_CONTENT'.

    Edge cases:
    - V=0, A=0 (neutral emotion preset): magnitude = 0 < THETA_NEUTRAL → NEUTRAL
    - V=0 boundary: treated as V≤0 path (Q2 or Q3 depending on A)
    - A=0 boundary: treated as A≥0 path (Q1 or Q2 depending on V)
    """
    if math.sqrt(V ** 2 + A ** 2) < THETA_NEUTRAL:
        return "NEUTRAL"
    if V <= 0 and A >= 0:
        return "Q2_STRESSED"
    if V <= 0 and A < 0:
        return "Q3_FATIGUED"
    if V > 0 and A >= 0:
        return "Q1_HAPPY"
    return "Q4_CONTENT"  # V > 0, A < 0


def zone_from_emotion(emotion_label: str) -> str:
    """Convenience: emotion string → zone via affect_mapper coordinates."""
    from engine.affect_mapper import emotion_to_va
    V, A = emotion_to_va(emotion_label)
    return classify_zone(V, A)
