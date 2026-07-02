"""Normalize raw emotion2vec+ labels to EmoEating's canonical 9-class vocabulary.

FunASR's emotion2vec+ emits labels that may differ from our canonical keys: an
"<unk>" token, Chinese glosses (e.g. "生气/angry"), or casing/whitespace variants.
This module folds any raw {label: score} dict onto exactly the 9 keys in
``config.EMOTION_VA``; unrecognized labels (including <unk>) collapse to "unknown".
"""
from __future__ import annotations

from emoeating.config import EMOTION_VA

CANONICAL_LABELS: tuple[str, ...] = tuple(EMOTION_VA)
_CANONICAL_SET = set(CANONICAL_LABELS)

# Lowercased raw token -> canonical key. The resolver also splits on "/" and
# whitespace, so gloss forms like "生气/angry" are handled without listing each.
RAW_TO_CANONICAL: dict[str, str] = {
    "happy": "happy",
    "angry": "angry",
    "sad": "sad",
    "fearful": "fearful",
    "fear": "fearful",
    "disgusted": "disgusted",
    "disgust": "disgusted",
    "surprised": "surprised",
    "surprise": "surprised",
    "neutral": "neutral",
    "other": "other",
    "unknown": "unknown",
    "unk": "unknown",
    "<unk>": "unknown",
}

assert set(RAW_TO_CANONICAL.values()) <= set(CANONICAL_LABELS), (
    "RAW_TO_CANONICAL values drifted from config.EMOTION_VA"
)


def canonical_for(raw_label: str) -> str:
    """Resolve a single raw label to a canonical key; unrecognized -> 'unknown'."""
    if not raw_label:
        return "unknown"
    text = raw_label.strip().lower()
    if text in RAW_TO_CANONICAL:
        return RAW_TO_CANONICAL[text]
    # Try sub-tokens of gloss/compound forms, e.g. "生气/angry" or "angry 愤怒".
    for token in text.replace("/", " ").split():
        if token in RAW_TO_CANONICAL:
            return RAW_TO_CANONICAL[token]
        if token in _CANONICAL_SET:
            return token
    return "unknown"


def normalize_emotion_scores(raw_scores: dict[str, float]) -> dict[str, float]:
    """Fold raw scores onto all 9 canonical keys, summing then renormalizing."""
    folded = {label: 0.0 for label in CANONICAL_LABELS}
    for raw_label, score in raw_scores.items():
        folded[canonical_for(raw_label)] += float(score)

    total = sum(folded.values())
    if total <= 0.0:
        fresh = {label: 0.0 for label in CANONICAL_LABELS}
        fresh["unknown"] = 1.0
        return fresh
    return {label: value / total for label, value in folded.items()}
