"""
SER inference module — public API and backend router (guide.md Phase 1 & 6).

Two swappable backends:
  "original"    — emotion2vec_plus_large 9-class off-the-shelf (Phase 1 baseline)
  "crema4class" — emotion2vec backbone + CREMA-D 4-class linear probe (Phase 7 upgrade)

Active backend is set by SER_BACKEND in config.py; switchable at runtime via
set_backend() (useful for debugging / A-B comparison without restarting).

Public API — stable across backends:
  predict_zone_from_audio(audio_bytes) -> (zone: str, probs: dict[str, float])
  is_available()  -> bool
  current_backend() -> {"id": str, "label": str, "n_classes": int}
  set_backend(backend_id: str)
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ── Active backend state ──────────────────────────────────────────────────────
try:
    from config import SER_BACKEND as _DEFAULT_BACKEND
except ImportError:
    _DEFAULT_BACKEND = "crema4class"

_VALID_BACKENDS = ("original", "crema4class")
_active_backend_id: str = _DEFAULT_BACKEND


def set_backend(backend_id: str) -> None:
    """Switch the active SER backend at runtime. Does not reload already-loaded models."""
    global _active_backend_id
    if backend_id not in _VALID_BACKENDS:
        raise ValueError(
            f"Unknown SER backend {backend_id!r}. Valid options: {_VALID_BACKENDS}"
        )
    if backend_id != _active_backend_id:
        logger.info("SER backend switched: %s → %s", _active_backend_id, backend_id)
        _active_backend_id = backend_id


def _mod():
    """Return the active backend module."""
    if _active_backend_id == "crema4class":
        from engine import _ser_crema as _backend
    else:
        from engine import _ser_original as _backend
    return _backend


# ── Public API ────────────────────────────────────────────────────────────────

def predict_zone_from_audio(audio_bytes: bytes) -> tuple[str, dict[str, float]]:
    """
    Single-pass SER inference.

    Args:
        audio_bytes: Raw WAV bytes (16 kHz mono recommended).

    Returns:
        zone  : one of {Q1_POS_ACT, Q2_NEG_ACT, Q3_NEG_DEACT, NEUTRAL_BASELINE}
        probs : class-probability dict (4-class or 9-class depending on backend)

    Raises:
        ImportError  — FunASR / modelscope not installed.
        RuntimeError — inference failure (corrupt audio, unsupported format, etc.).
    """
    return _mod().predict_zone_from_audio(audio_bytes)


def is_available() -> bool:
    """Return True if the active backend's dependencies are satisfied."""
    return _mod().is_available()


def current_backend() -> dict:
    """Return metadata for the active backend: id, label, n_classes."""
    m = _mod()
    return {
        "id":        m.BACKEND_ID,
        "label":     m.BACKEND_LABEL,
        "n_classes": m.N_CLASSES,
    }
