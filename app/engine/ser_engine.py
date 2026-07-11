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
  is_remote_configured() -> bool

Local vs. remote routing:
  If config.SER_REMOTE_URL is set, all three public calls above are proxied
  to a remote copy of this same module (see engine/_ser_remote.py and
  server/main.py) instead of importing funasr in-process — Streamlit
  Community Cloud's RAM budget can't load emotion2vec_plus_large. Local dev
  leaves SER_REMOTE_URL unset and nothing changes. Both routes run the
  identical backend code, so results are the same regardless of location.
"""

from __future__ import annotations

import logging

from config import SER_MODEL_ID, SER_REMOTE_URL

logger = logging.getLogger(__name__)

# ── Active backend state ──────────────────────────────────────────────────────
try:
    from config import SER_BACKEND as _DEFAULT_BACKEND
except ImportError:
    _DEFAULT_BACKEND = "crema4class"

_VALID_BACKENDS = ("original", "crema4class")
_active_backend_id: str = _DEFAULT_BACKEND

# Metadata mirror of _ser_crema.BACKEND_LABEL/N_CLASSES and
# _ser_original.BACKEND_LABEL/N_CLASSES — duplicated here (rather than
# imported) so current_backend() never has to import _ser_crema.py, which
# pulls in torch at module scope and would defeat the point of the lean
# cloud install when routing remotely. "original"'s label is derived from
# SER_MODEL_ID (like _ser_original.py's own BACKEND_LABEL) rather than
# hardcoded, so a remote-mode researcher sees the actual configured backbone.
_BACKEND_META = {
    "crema4class": {"label": "emotion2vec + CREMA-D probe (4-class)", "n_classes": 4},
    "original":    {"label": f"{SER_MODEL_ID.rsplit('/', 1)[-1]} (9-class)", "n_classes": 9},
}


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
    """Return the active LOCAL backend module (funasr in-process)."""
    if _active_backend_id == "crema4class":
        from engine import _ser_crema as _backend
    else:
        from engine import _ser_original as _backend
    return _backend


def is_remote_configured() -> bool:
    """True if this deployment routes SER inference to a remote server
    (config.SER_REMOTE_URL set) rather than running funasr in-process."""
    return bool(SER_REMOTE_URL)


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
        ImportError  — FunASR / modelscope not installed (local mode only).
        RuntimeError — inference failure (corrupt audio, unsupported format,
            remote endpoint unreachable/misconfigured, etc.).
    """
    if is_remote_configured():
        from engine import _ser_remote
        logger.info("SER inference routed to remote server (backend=%s).", _active_backend_id)
        return _ser_remote.predict_zone_from_audio(audio_bytes, _active_backend_id)
    logger.info("SER inference routed to local backend (backend=%s).", _active_backend_id)
    return _mod().predict_zone_from_audio(audio_bytes)


def is_available() -> bool:
    """Return True if the active backend's dependencies are satisfied."""
    if is_remote_configured():
        from engine import _ser_remote
        return _ser_remote.is_available()
    return _mod().is_available()


def current_backend() -> dict:
    """Return metadata for the active backend: id, label, n_classes."""
    if is_remote_configured():
        meta = _BACKEND_META[_active_backend_id]
        return {
            "id":        _active_backend_id,
            "label":     f"{meta['label']} (remote)",
            "n_classes": meta["n_classes"],
        }
    m = _mod()
    return {
        "id":        m.BACKEND_ID,
        "label":     m.BACKEND_LABEL,
        "n_classes": m.N_CLASSES,
    }
