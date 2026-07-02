"""ConfidenceEngine: EMA-based zone confidence from rolling speech windows.

Pure logic — no I/O, no async, no model. Independently unit-testable.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal

from emoeating.affect.mapping import to_valence_arousal
from emoeating.config import (
    EMA_ALPHA,
    EMOTION_ZONE,
    MARGIN_THETA,
    MIN_WINDOW_CONF,
    SAFETY_NEG_THRESHOLD,
    SPEECH_FLOOR_S,
    STABILITY_N,
    TIMEOUT_S,
)

# Ordered tuple preserves deterministic argmax tie-breaking.
_VALID_ZONES: tuple[str, ...] = ("POS_ACTIVE", "NEG_ACTIVE", "NEG_DEACTIVE", "NEUTRAL_CALM")
_NEG_ZONES: frozenset[str] = frozenset({"NEG_ACTIVE", "NEG_DEACTIVE"})
_ALL_LABELS: list[str] = list(EMOTION_ZONE)  # insertion order from config


def _uniform_ema() -> dict[str, float]:
    n = len(_ALL_LABELS)
    return {label: 1.0 / n for label in _ALL_LABELS}


def _zone_masses(ema: dict[str, float]) -> dict[str, float]:
    masses: dict[str, float] = {z: 0.0 for z in _VALID_ZONES}
    for label, prob in ema.items():
        masses[EMOTION_ZONE[label]] += prob
    return masses


@dataclass(frozen=True)
class ConfidenceState:
    leading_zone: str
    confidence: float
    margin: float
    speech_elapsed: float
    wall_elapsed: float
    decision: Literal["CONTINUE", "STOP"]
    safety_flag: bool = False


class ConfidenceEngine:
    """Maintains an EMA of per-window emotion distributions and derives zone confidence.

    All parameters default to the tunable config knobs so production code
    constructs with ``ConfidenceEngine()`` while tests can inject small values.
    """

    def __init__(
        self,
        ema_alpha: float = EMA_ALPHA,
        min_window_conf: float = MIN_WINDOW_CONF,
        speech_floor_s: float = SPEECH_FLOOR_S,
        stability_n: int = STABILITY_N,
        margin_theta: float = MARGIN_THETA,
        timeout_s: float = TIMEOUT_S,
        safety_neg_threshold: float = SAFETY_NEG_THRESHOLD,
    ) -> None:
        self._alpha = ema_alpha
        self._min_conf = min_window_conf
        self._floor = speech_floor_s
        self._stability_n = stability_n
        self._margin_theta = margin_theta
        self._timeout = timeout_s
        self._safety_thresh = safety_neg_threshold
        self._ema: dict[str, float] = _uniform_ema()
        self._speech_elapsed: float = 0.0
        self._history: deque[str] = deque(maxlen=stability_n)
        # Tracks whether NEG mass >= threshold for each recent *quality* update.
        # safety_flag fires only when every entry in this window is True.
        self._neg_streak: deque[bool] = deque(maxlen=stability_n)
        self._best: ConfidenceState | None = None
        self._done: bool = False

    def reset(self) -> None:
        self._ema = _uniform_ema()
        self._speech_elapsed = 0.0
        self._history.clear()
        self._neg_streak.clear()
        self._best = None
        self._done = False

    def update(
        self, probs: dict[str, float], speech_dt: float, wall_t: float
    ) -> ConfidenceState:
        """Process one window's emotion probs; return current ConfidenceState.

        Args:
            probs: 9-class emotion probabilities (need not sum to 1; normalized internally).
            speech_dt: seconds of user speech in this window (0 if silent/agent).
            wall_t: wall-clock elapsed seconds since session start.
        """
        if self._done:
            assert self._best is not None
            return self._best

        # --- Per-window quality gate ---
        dom_prob = max(probs.values(), default=0.0)
        quality = dom_prob >= self._min_conf

        if quality:
            total = sum(probs.values()) or 1.0
            norm = {k: v / total for k, v in probs.items()}
            for label in _ALL_LABELS:
                self._ema[label] = (
                    self._alpha * norm.get(label, 0.0)
                    + (1.0 - self._alpha) * self._ema[label]
                )
            ema_sum = sum(self._ema.values()) or 1.0
            self._ema = {k: v / ema_sum for k, v in self._ema.items()}
            self._speech_elapsed += speech_dt

        # --- Zone masses from current EMA ---
        masses = _zone_masses(self._ema)
        sorted_zones = sorted(masses.items(), key=lambda kv: kv[1], reverse=True)
        leading = sorted_zones[0][0]
        confidence = sorted_zones[0][1]
        second = sorted_zones[1][1] if len(sorted_zones) > 1 else 0.0
        margin = confidence - second

        if quality:
            self._history.append(leading)

        # --- Safety flag: combined NEG zone mass, must be SUSTAINED across STABILITY_N
        # consecutive quality updates (spec §4: "strong SUSTAINED NEG"). Non-quality
        # windows are ignored so low-confidence frames can't pollute the streak.
        neg_mass = sum(masses[z] for z in _NEG_ZONES)
        if quality:
            self._neg_streak.append(neg_mass >= self._safety_thresh)
        safety_flag = (
            len(self._neg_streak) >= self._stability_n
            and all(self._neg_streak)
        )

        state = ConfidenceState(
            leading_zone=leading,
            confidence=confidence,
            margin=margin,
            speech_elapsed=self._speech_elapsed,
            wall_elapsed=wall_t,
            decision="CONTINUE",
            safety_flag=safety_flag,
        )

        if self._best is None or confidence > self._best.confidence:
            self._best = state

        # --- STOP conditions ---
        stable = (
            len(self._history) >= self._stability_n
            and len(set(self._history)) == 1
        )
        speech_stop = (
            self._speech_elapsed >= self._floor and stable and margin >= self._margin_theta
        )
        timeout_stop = wall_t >= self._timeout

        if speech_stop or timeout_stop:
            self._done = True
            if timeout_stop and not speech_stop:
                # Best-so-far path: use the highest-confidence zone seen.
                best = self._best
                return ConfidenceState(
                    leading_zone=best.leading_zone,
                    confidence=best.confidence,
                    margin=best.margin,
                    speech_elapsed=self._speech_elapsed,
                    wall_elapsed=wall_t,
                    decision="STOP",
                    safety_flag=safety_flag,
                )
            return ConfidenceState(
                leading_zone=leading,
                confidence=confidence,
                margin=margin,
                speech_elapsed=self._speech_elapsed,
                wall_elapsed=wall_t,
                decision="STOP",
                safety_flag=safety_flag,
            )

        return state

    def final_infer(self) -> dict:
        """Return an InferResult-compatible dict derived from the current EMA.

        ``emotion_probs``: current EMA (9-class, sums to 1).
        ``valence/arousal``: dominant-class placement via to_valence_arousal.
        ``zone``: argmax of zone masses from the EMA.

        Note: ``zone`` (mass-argmax) and ``valence``/``arousal`` (dominant-class
        placement) can disagree on a near-uniform EMA — e.g. the argmax zone may
        be NEUTRAL_CALM while the dominant class pulls valence/arousal slightly
        negative.  The converse route renders only ``zone`` + ``emotion_probs``;
        ``valence`` and ``arousal`` are provided for downstream components only.
        """
        valence, arousal = to_valence_arousal(self._ema)
        masses = _zone_masses(self._ema)
        leading = max(masses, key=masses.__getitem__)
        return {
            "emotion_probs": dict(self._ema),
            "valence": float(valence),
            "arousal": float(arousal),
            "zone": leading,
        }
