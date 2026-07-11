"""
SER Backend A: emotion2vec+ off-the-shelf, 9-class (size set by config.SER_MODEL_ID).

Original Phase 1 implementation (guide.md Phase 1 & 6). Size-agnostic — uses
the model's own built-in classification head, so it works with any
emotion2vec+ checkpoint (seed/base/large) with zero retraining, unlike the
CREMA-D linear probe in _ser_crema.py.
Single-pass: 16 kHz mono WAV → 9-class softmax → per-zone probability mass →
max-mass zone. Marginalising over SER_EMOTION_TO_ZONE (rather than taking the
argmax class first) uses the full distribution, since three classes
(angry/disgusted/fearful) share Q2_NEG_ACT and can jointly outweigh a lone
higher-probability class from another zone.
Ma et al. (2024), Findings of ACL 2024. DOI: 10.18653/v1/2024.findings-acl.931
"""

from __future__ import annotations

import os
import tempfile
import logging

from config import SER_MODEL_ID as _SER_MODEL_ID

logger = logging.getLogger(__name__)

BACKEND_ID    = "original"
# Derived from config.SER_MODEL_ID (not hardcoded) so the UI/debug panel
# always names the backbone actually running, not a stale literal — this
# label is user/researcher-facing (03_emotion.py's spinner text and the
# ?debug=1 backend selector) and matters for methodological transparency.
BACKEND_LABEL = f"{_SER_MODEL_ID.rsplit('/', 1)[-1]} (9-class)"
N_CLASSES     = 9

_model = None


def _get_model():
    global _model
    if _model is not None:
        return _model
    try:
        from funasr import AutoModel  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "FunASR is not installed. Run:\n"
            "  pip install funasr modelscope\n"
            "then restart the application."
        ) from exc
    from config import SER_MODEL_ID
    logger.info("Loading emotion2vec_plus_large (9-class) — first call only...")
    _model = AutoModel(
        model=SER_MODEL_ID,
        trust_remote_code=True,
        disable_update=True,
    )
    logger.info("emotion2vec_plus_large (9-class) loaded.")
    return _model


def predict_zone_from_audio(audio_bytes: bytes) -> tuple[str, dict[str, float]]:
    """16 kHz WAV bytes → (canonical zone, 9-class prob dict)."""
    from config import SER_EMOTION_TO_ZONE, SER_EMOTION_CLASSES

    model = _get_model()
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
    try:
        with os.fdopen(tmp_fd, "wb") as f:
            f.write(audio_bytes)
        result = model.generate(
            input=tmp_path,
            granularity="utterance",
            extract_embedding=False,
        )
    except Exception as exc:
        raise RuntimeError(f"SER inference failed: {exc}") from exc
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    probs: dict[str, float] = {}
    try:
        entry = result[0] if isinstance(result, list) and result else {}
        raw_labels = entry.get("labels", SER_EMOTION_CLASSES)
        raw_scores = entry.get("scores", [1.0 / 9] * len(SER_EMOTION_CLASSES))
        for lab, sc in zip(raw_labels, raw_scores):
            clean = lab.split("/")[-1].lower().strip()
            probs[clean] = float(sc)
    except Exception as exc:
        logger.warning("Could not parse SER output; using uniform distribution. %s", exc)
        probs = {e: 1.0 / 9 for e in SER_EMOTION_CLASSES}

    for cls in SER_EMOTION_CLASSES:
        probs.setdefault(cls, 0.0)

    zone_mass: dict[str, float] = dict.fromkeys(set(SER_EMOTION_TO_ZONE.values()), 0.0)
    for cls, p in probs.items():
        zone_mass[SER_EMOTION_TO_ZONE.get(cls, "NEUTRAL_BASELINE")] += p
    zone = max(zone_mass, key=zone_mass.get)
    return zone, probs


def is_available() -> bool:
    try:
        import funasr  # noqa: F401
        return True
    except ImportError:
        return False
