"""Unit tests for engine/affect_mapper.py"""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import pytest
from engine.affect_mapper import emotion_to_va, get_emotion_metadata
from config import EMOTION_COORDS


def test_all_emotions_return_valid_va():
    """All 11 emotions must map to (V, A) within [-1, 1]."""
    for emotion in EMOTION_COORDS:
        V, A = emotion_to_va(emotion)
        assert -1.0 <= V <= 1.0, f"{emotion}: V={V} out of range"
        assert -1.0 <= A <= 1.0, f"{emotion}: A={A} out of range"


def test_emotion_coords_count():
    """Must have exactly 11 emotion classes."""
    assert len(EMOTION_COORDS) == 11


def test_case_insensitive():
    """Emotion labels should be case-insensitive."""
    V1, A1 = emotion_to_va("happy")
    V2, A2 = emotion_to_va("HAPPY")
    V3, A3 = emotion_to_va("Happy")
    assert V1 == V2 == V3
    assert A1 == A2 == A3


def test_unknown_emotion_raises():
    with pytest.raises(ValueError):
        emotion_to_va("euphoric")


def test_positive_valence_emotions():
    """happy, excited, content, calm should have positive valence."""
    for emo in ["happy", "excited", "content", "calm"]:
        V, _ = emotion_to_va(emo)
        assert V > 0, f"{emo}: expected V > 0, got {V}"


def test_negative_valence_emotions():
    """sad, angry, anxious, stressed should have negative valence."""
    for emo in ["sad", "angry", "anxious", "stressed"]:
        V, _ = emotion_to_va(emo)
        assert V < 0, f"{emo}: expected V < 0, got {V}"


def test_high_arousal_emotions():
    """excited, angry, stressed, anxious should have A > 0.5."""
    for emo in ["excited", "angry", "stressed", "anxious"]:
        _, A = emotion_to_va(emo)
        assert A > 0.5, f"{emo}: expected A > 0.5, got {A}"


def test_low_arousal_emotions():
    """tired, calm should have A < -0.5."""
    for emo in ["tired", "calm"]:
        _, A = emotion_to_va(emo)
        assert A < -0.5, f"{emo}: expected A < -0.5, got {A}"


def test_neutral_is_origin():
    """neutral should be near (0, 0)."""
    V, A = emotion_to_va("neutral")
    assert abs(V) < 0.05
    assert abs(A) < 0.05


def test_metadata_has_required_keys():
    for emotion in EMOTION_COORDS:
        meta = get_emotion_metadata(emotion)
        assert "V" in meta
        assert "A" in meta
        assert "emoji" in meta
        assert "color" in meta
        assert meta["color"].startswith("#")
