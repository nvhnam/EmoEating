"""
Maps an emotion label (string) to (Valence, Arousal) coordinates.
Provides stub for future voice-based detection.

Russell Circumplex Model: Russell, J. A. (1980). A circumplex model of affect.
Journal of Personality and Social Psychology, 39(6), 1161â€“1178.
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


def detect_from_audio(audio_bytes: bytes, api_endpoint: str = None) -> str:
    """
    STUB â€” Voice emotion detection.

    When implemented:
    - POST audio_bytes to api_endpoint (WAV or MP3)
    - Receive: {"emotion": str, "confidence": float, "probabilities": {...}}
    - Return emotion label string matching EMOTION_COORDS keys

    Expected API endpoint: http://localhost:8001/predict
    """
    raise NotImplementedError(
        "Voice emotion detection not yet integrated. "
        "Implement by replacing this stub with your voice model API call. "
        "Expected return: emotion label string matching EMOTION_COORDS keys."
    )
