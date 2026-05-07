"""Input validation helpers."""

from __future__ import annotations

def validate_profile_inputs(age, sex, height_cm, weight_kg) -> list[str]:
    """Return list of error messages; empty list means all valid."""
    errors = []
    if age is not None:
        if not (18 <= age <= 90):
            errors.append("Age must be between 18 and 90.")
    if height_cm is not None:
        if not (100 <= height_cm <= 250):
            errors.append("Height must be between 100 and 250 cm.")
    if weight_kg is not None:
        if not (30.0 <= weight_kg <= 300.0):
            errors.append("Weight must be between 30 and 300 kg.")
    return errors


def validate_emotion(emotion_label: str) -> bool:
    from config import EMOTION_COORDS
    return emotion_label.lower().strip() in EMOTION_COORDS


def sanitize_string(s: str, max_length: int = 255) -> str:
    if not s:
        return ""
    return str(s).strip()[:max_length]
