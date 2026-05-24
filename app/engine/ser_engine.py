"""
Phase 1 — SER inference module (guide.md Phase 1 & 6).

emotion2vec_plus_large off-the-shelf via FunASR AutoModel.
Single-pass: 16 kHz mono WAV → 9-class softmax → argmax → zone lookup.

Ma, Z., et al. (2024). emotion2vec: Self-Supervised Pre-Training for Speech Emotion
  Representation. Findings of ACL 2024. DOI: 10.18653/v1/2024.findings-acl.931

Model: iic/emotion2vec_plus_large (~300M params)
Input: 16 kHz mono WAV (utterance-level granularity)
Output: 9-class probability distribution
  [angry, disgusted, fearful, happy, neutral, other, sad, surprised, unknown]

Zone lookup (guide.md Phase 2 canonical table):
  Q1_POS_ACT       ← happy, surprised
  Q2_NEG_ACT       ← angry, disgusted, fearful
  Q3_NEG_DEACT     ← sad
  NEUTRAL_BASELINE ← neutral, other, unknown

Architectural invariants (guide.md Phase 6):
  - Single-pass only. No fine-tuning, no ensembling.
  - Returns BOTH zone AND raw 9-class probability vector for confusion-matrix reporting.
  - FunASR is the inference framework; do not replace.
"""

from __future__ import annotations

import os
import io
import tempfile
import logging

logger = logging.getLogger(__name__)

# Lazy-loaded model — loaded once on first call
_model = None


def _get_model():
    """Load emotion2vec_plus_large via FunASR AutoModel (lazy singleton)."""
    global _model
    if _model is not None:
        return _model

    try:
        from funasr import AutoModel  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "FunASR is not installed. Run:\n"
            "  pip install funasr modelscope\n"
            "then restart the application to enable voice-based emotion detection."
        ) from exc

    from config import SER_MODEL_ID
    logger.info("Loading emotion2vec_plus_large — first call only (~300M params)...")
    _model = AutoModel(
        model=SER_MODEL_ID,
        trust_remote_code=True,
        disable_update=True,
    )
    logger.info("emotion2vec_plus_large loaded.")
    return _model


def predict_zone_from_audio(
    audio_bytes: bytes,
) -> tuple[str, dict[str, float]]:
    """
    Single-pass SER inference.

    Args:
        audio_bytes: Raw WAV bytes (16 kHz mono recommended; other rates accepted
                     but may degrade accuracy — resample externally if needed).

    Returns:
        zone  : str — one of {Q1_POS_ACT, Q2_NEG_ACT, Q3_NEG_DEACT, NEUTRAL_BASELINE}
        probs : dict[str, float] — 9-class softmax probability distribution
                                   (required for confusion-matrix reporting, guide §7.1)

    Raises:
        ImportError  — if FunASR / modelscope is not installed.
        RuntimeError — if inference fails (corrupt audio, unsupported format, etc.).
    """
    from config import SER_EMOTION_TO_ZONE, SER_EMOTION_CLASSES

    model = _get_model()

    # Write audio bytes to a temp file — FunASR AutoModel.generate() requires a path.
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

    # Parse FunASR emotion2vec output.
    # Expected format: [{"key": "...", "labels": [...], "scores": [...]}]
    # Label strings may carry language prefixes, e.g. "angry/angry" → strip prefix.
    probs: dict[str, float] = {}
    try:
        entry = result[0] if isinstance(result, list) and result else {}
        raw_labels = entry.get("labels", SER_EMOTION_CLASSES)
        raw_scores = entry.get("scores", [1 / 9] * len(SER_EMOTION_CLASSES))

        for lab, sc in zip(raw_labels, raw_scores):
            # Strip language prefix if present ("angry/angry" → "angry")
            clean_lab = lab.split("/")[-1].lower().strip()
            probs[clean_lab] = float(sc)
    except Exception as exc:
        logger.warning("Could not parse SER output; using uniform distribution. %s", exc)
        probs = {e: 1.0 / 9 for e in SER_EMOTION_CLASSES}

    # Fill in any missing classes with 0.0 for a complete 9-class dict
    for cls in SER_EMOTION_CLASSES:
        probs.setdefault(cls, 0.0)

    # argmax → zone lookup (single-pass, no ensembling — guide §6.1)
    top_emotion = max(probs, key=probs.get)
    zone = SER_EMOTION_TO_ZONE.get(top_emotion, "NEUTRAL_BASELINE")

    return zone, probs


def is_available() -> bool:
    """Return True if FunASR is installed and model can be loaded."""
    try:
        import funasr  # noqa: F401
        return True
    except ImportError:
        return False
