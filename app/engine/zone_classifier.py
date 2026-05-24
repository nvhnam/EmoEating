"""
Stage 2: Classifies (Valence, Arousal) into 4 emotional zones per Russell (1980) circumplex.

4-zone reframe (guide.md Phase 2):
  Q1_POS_ACT       : +V, +A  (pleasant + high arousal)
  Q2_NEG_ACT       : -V, +A  (unpleasant + high arousal)
  Q3_NEG_DEACT     : -V, -A  (unpleasant + low arousal)
  NEUTRAL_BASELINE : near origin OR +V, -A (positive low-arousal merged with neutral)

Rationale for Q4 → NEUTRAL_BASELINE merge:
  Valence at low arousal is the least recoverable affective dimension from
  prosody-only SER (Posner, Russell & Peterson 2005, Dev Psychopathology 17:715–734).
  Calm (+V, −A) and Neutral (V≈0, −A) share their acoustic signature; the
  RAVDESS _calm_ category is absent from CREMA-D, IEMOCAP, MSP-Podcast, MELD.

Russell, J. A. (1980). A circumplex model of affect.
  Journal of Personality and Social Psychology, 39(6), 1161–1178.
Posner, J., Russell, J. A., & Peterson, B. S. (2005).
  Development and Psychopathology, 17(3), 715–734. DOI:10.1017/S0954579405050340

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
    Map (Valence, Arousal) to one of four emotional zones.

    Returns one of:
      'Q1_POS_ACT'       — +V, +A   (happy, excited)
      'Q2_NEG_ACT'       — -V, +A   (stressed, anxious, angry)
      'Q3_NEG_DEACT'     — -V, -A   (sad, tired, bored)
      'NEUTRAL_BASELINE' — near origin OR +V, -A (calm/content → merged per guide)

    Edge cases:
      V=0, A=0: magnitude=0 < THETA_NEUTRAL → NEUTRAL_BASELINE
      V=0 boundary: treated as V≤0 (Q2 or Q3 depending on A)
      A=0 boundary: treated as A≥0 (Q1 or Q2 depending on V)
    """
    magnitude = math.sqrt(V ** 2 + A ** 2)
    if magnitude < THETA_NEUTRAL:
        return "NEUTRAL_BASELINE"
    if V <= 0 and A >= 0:
        return "Q2_NEG_ACT"
    if V <= 0 and A < 0:
        return "Q3_NEG_DEACT"
    if V > 0 and A >= 0:
        return "Q1_POS_ACT"
    # V > 0, A < 0: positive deactivation (calm/content) → merged into Neutral Baseline
    return "NEUTRAL_BASELINE"


def zone_from_emotion(emotion_label: str) -> str:
    """Convenience: emotion string → zone via affect_mapper VA coordinates."""
    from engine.affect_mapper import emotion_to_va
    V, A = emotion_to_va(emotion_label)
    return classify_zone(V, A)
