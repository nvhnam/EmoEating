"""Speech-emotion encoders. The Protocol lets the rest of the system and the test
suite depend on an abstraction, so only ONE gated test ever loads the real model.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from emoeating.ser.labels import normalize_emotion_scores

# Fixed default for MockEncoder: neutral-dominant, deterministic.
_DEFAULT_MOCK_SCORES: dict[str, float] = {"neutral": 0.6, "happy": 0.2, "sad": 0.2}


@runtime_checkable
class Encoder(Protocol):
    """Maps a mono 16 kHz float32 waveform to canonical 9-class probabilities."""

    def predict(self, waveform: np.ndarray) -> dict[str, float]: ...


class MockEncoder:
    """Deterministic encoder for tests and wiring; never loads a model.

    ``scores`` may use raw or canonical labels; it is normalized onto the
    canonical 9-class vocabulary on every ``predict`` call.
    """

    def __init__(self, scores: dict[str, float] | None = None) -> None:
        self._scores = dict(scores) if scores is not None else dict(_DEFAULT_MOCK_SCORES)

    def predict(self, waveform: np.ndarray) -> dict[str, float]:
        return normalize_emotion_scores(self._scores)


class Emotion2VecEncoder:
    """Real emotion2vec+_large encoder via FunASR. Model loads lazily and is cached.

    Heavy (torch + funasr + ~hundreds of MB of weights); CPU inference is fine for
    3-5s clips. Never imported at module load — only inside ``_get_model``.
    """

    def __init__(
        self, model_id: str = "iic/emotion2vec_plus_large", device: str | None = None
    ) -> None:
        self._model_id = model_id
        self._device = device
        self._model = None  # lazy

    def _get_model(self):
        if self._model is None:
            from funasr import AutoModel  # heavy import, deferred

            kwargs = {"model": self._model_id}
            if self._device is not None:
                kwargs["device"] = self._device
            self._model = AutoModel(**kwargs)
        return self._model

    def predict(self, waveform: np.ndarray) -> dict[str, float]:
        model = self._get_model()
        results = model.generate(
            np.asarray(waveform, dtype=np.float32),
            granularity="utterance",
            extract_embedding=False,
        )
        if not results:
            raise RuntimeError("emotion2vec returned no result")
        item = results[0]
        labels = item.get("labels")
        scores = item.get("scores")
        if labels is None or scores is None or len(labels) != len(scores):
            raise RuntimeError(f"unexpected emotion2vec result shape: {item!r}")
        raw = {str(lbl): float(sc) for lbl, sc in zip(labels, scores)}
        return normalize_emotion_scores(raw)
