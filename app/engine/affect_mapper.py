"""
Maps an emotion label (string) to (Valence, Arousal) coordinates.
Routes voice-based detection to the SER engine (Phase 1).

Manual path  : emotion label → EMOTION_COORDS → (V, A) → classify_zone()
SER path     : audio bytes → ser_engine.predict_zone_from_audio() → (zone, probs_9class)
               VA coordinates are not used in the SER path — zone is returned directly.

Russell Circumplex Model: Russell, J. A. (1980). A circumplex model of affect.
  Journal of Personality and Social Psychology, 39(6), 1161–1178.
"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import EMOTION_COORDS


def emotion_to_va(emotion_label: str) -> tuple[float, float]:
    """Map emotion string to (Valence, Arousal) from Russell Circumplex."""
    label = emotion_label.lower().strip()
    if label not in EMOTION_COORDS:
        raise ValueError(
            f"Unknown emotion: '{emotion_label}'. "
            f"Valid emotions: {list(EMOTION_COORDS.keys())}"
        )
    coords = EMOTION_COORDS[label]
    return coords["V"], coords["A"]


def get_emotion_metadata(emotion_label: str) -> dict:
    """Return full metadata dict for an emotion (V, A, emoji, color)."""
    label = emotion_label.lower().strip()
    if label not in EMOTION_COORDS:
        raise ValueError(f"Unknown emotion: '{emotion_label}'")
    return EMOTION_COORDS[label]


def detect_from_audio(audio_bytes: bytes) -> tuple[str, dict[str, float]]:
    """
    Voice emotion detection via emotion2vec_plus_large (SER path).

    Args:
        audio_bytes: Raw WAV bytes (16 kHz mono recommended).

    Returns:
        (zone, probs_9class) where:
          zone        : str — one of {Q1_POS_ACT, Q2_NEG_ACT, Q3_NEG_DEACT, NEUTRAL_BASELINE}
          probs_9class: dict[str, float] — 9-class probability distribution

    Raises:
        ImportError  — FunASR not installed (pip install funasr modelscope).
        RuntimeError — Inference failed (corrupt audio, etc.).
    """
    from engine.ser_engine import predict_zone_from_audio
    return predict_zone_from_audio(audio_bytes)
