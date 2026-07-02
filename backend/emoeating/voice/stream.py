"""RollingWindow: buffers Int16 PCM frames → overlapping windows → encoder → engine."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

import numpy as np

from emoeating.config import HOP_S, WINDOW_S
from emoeating.voice.confidence import ConfidenceEngine, ConfidenceState

if TYPE_CHECKING:
    from emoeating.ser.encoder import Encoder

_SR = 16_000
_VAD_RMS_FLOOR = 50.0  # RMS of Int16 samples; above = user speech


class RollingWindow:
    """Accumulates PCM, fires overlapping 3s windows at 1s hop, gates on VAD + agent flag.

    Backpressure rule: if the buffer depth after processing a window still exceeds
    (window_samples + hop_samples), the next window is *skipped* (hop advanced
    without encoding) to avoid unbounded queuing under slow inference.
    """

    def __init__(
        self,
        encoder: Encoder,
        engine: ConfidenceEngine,
        sample_rate: int = _SR,
        window_s: float = WINDOW_S,
        hop_s: float = HOP_S,
        vad_rms_floor: float = _VAD_RMS_FLOOR,
    ) -> None:
        self._encoder = encoder
        self._engine = engine
        self._sr = sample_rate
        self._window_n = int(window_s * sample_rate)
        self._hop_n = int(hop_s * sample_rate)
        self._vad_floor = vad_rms_floor
        self._buf: np.ndarray = np.empty(0, dtype=np.int16)
        self._agent_speaking: bool = False
        self._start_t: float = time.monotonic()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def set_agent_speaking(self, speaking: bool) -> None:
        """Gate: when True the next window(s) will be dropped without encoding."""
        self._agent_speaking = speaking

    def reset(self) -> None:
        """Discard all buffered PCM and reset the engine (called on reconnect)."""
        self._buf = np.empty(0, dtype=np.int16)
        self._agent_speaking = False
        self._start_t = time.monotonic()
        self._engine.reset()

    def push_pcm(self, frame: bytes) -> list[ConfidenceState]:
        """Append a raw Int16 LE PCM frame; return ConfidenceStates for each window encoded."""
        chunk = np.frombuffer(frame, dtype=np.int16)
        self._buf = (
            np.concatenate([self._buf, chunk]) if len(self._buf) else chunk.copy()
        )

        results: list[ConfidenceState] = []
        while len(self._buf) >= self._window_n:
            # --- Backpressure: skip (no encode) when buffer is too deep ---
            if results and len(self._buf) > self._window_n + self._hop_n:
                self._buf = self._buf[self._hop_n:].copy()
                continue

            window = self._buf[: self._window_n]
            self._buf = self._buf[self._hop_n :].copy()

            # --- Agent-speaking gate (echo defense) ---
            if self._agent_speaking:
                continue

            # --- VAD / energy gate ---
            rms = float(np.sqrt(np.mean(window.astype(np.float32) ** 2)))
            speech_dt = (self._hop_n / self._sr) if rms >= self._vad_floor else 0.0

            # --- Encode → engine update ---
            waveform = window.astype(np.float32) / 32768.0
            probs = self._encoder.predict(waveform)
            wall_t = time.monotonic() - self._start_t
            state = self._engine.update(probs, speech_dt, wall_t)
            results.append(state)

        return results
