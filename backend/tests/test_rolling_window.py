"""Tests for RollingWindow: cadence, VAD, agent-overlap drop, backpressure."""
import numpy as np
import pytest

from emoeating.ser.encoder import MockEncoder
from emoeating.voice.confidence import ConfidenceEngine, ConfidenceState
from emoeating.voice.stream import RollingWindow

SR = 16_000
WINDOW_N = 3 * SR   # 48 000 samples
HOP_N = 1 * SR      # 16 000 samples


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sine_pcm(n_samples: int, amplitude: int = 4000, freq: float = 440.0) -> bytes:
    """Loud sine wave as raw Int16 LE PCM (RMS well above VAD floor)."""
    t = np.arange(n_samples, dtype=np.float32)
    sig = (amplitude * np.sin(2.0 * np.pi * freq * t / SR)).astype(np.int16)
    return sig.tobytes()


def _silent_pcm(n_samples: int) -> bytes:
    return b"\x00" * (n_samples * 2)


def _make_engine() -> ConfidenceEngine:
    return ConfidenceEngine(
        speech_floor_s=3.0, stability_n=3, margin_theta=0.05, timeout_s=9999.0
    )


def _make_encoder(scores: dict | None = None) -> MockEncoder:
    raw = scores or {"sad": 0.8, "neutral": 0.15, "other": 0.05}
    return MockEncoder(raw)


# ---------------------------------------------------------------------------
# Test 1: window / hop cadence
# ---------------------------------------------------------------------------

def test_first_window_fires_after_window_samples():
    enc = _make_encoder()
    eng = _make_engine()
    rw = RollingWindow(encoder=enc, engine=eng, sample_rate=SR,
                       window_s=3.0, hop_s=1.0)

    # One sample less than WINDOW_N → no window yet
    states = rw.push_pcm(_sine_pcm(WINDOW_N - 1))
    assert states == []

    # One more sample → exactly WINDOW_N → first window fires
    states = rw.push_pcm(_sine_pcm(1))
    assert len(states) == 1


def test_second_window_fires_after_one_hop():
    enc = _make_encoder()
    eng = _make_engine()
    rw = RollingWindow(encoder=enc, engine=eng, sample_rate=SR,
                       window_s=3.0, hop_s=1.0)

    rw.push_pcm(_sine_pcm(WINDOW_N))   # first window
    states = rw.push_pcm(_sine_pcm(HOP_N))  # exactly one hop more → second window
    assert len(states) == 1


def test_no_window_before_full_window_accumulated():
    enc = _make_encoder()
    eng = _make_engine()
    rw = RollingWindow(encoder=enc, engine=eng, sample_rate=SR,
                       window_s=3.0, hop_s=1.0)

    # Send several small chunks that total less than WINDOW_N
    for _ in range(10):
        states = rw.push_pcm(_sine_pcm(1000))  # 1000 samples each
    # 10 000 samples total < 48 000
    assert states == []


# ---------------------------------------------------------------------------
# Test 2: speech-time accounting via VAD
# ---------------------------------------------------------------------------

def test_speech_dt_zero_for_silent_window():
    enc = _make_encoder()
    eng = _make_engine()
    rw = RollingWindow(encoder=enc, engine=eng, sample_rate=SR,
                       window_s=3.0, hop_s=1.0)

    rw.push_pcm(_silent_pcm(WINDOW_N))
    assert eng._speech_elapsed == 0.0  # silence → VAD gate → speech_dt=0


def test_speech_dt_nonzero_for_loud_window():
    enc = _make_encoder()
    eng = _make_engine()
    rw = RollingWindow(encoder=enc, engine=eng, sample_rate=SR,
                       window_s=3.0, hop_s=1.0)

    rw.push_pcm(_sine_pcm(WINDOW_N))  # loud sine → VAD passes
    assert eng._speech_elapsed == pytest.approx(1.0)  # one hop worth of speech


# ---------------------------------------------------------------------------
# Test 3: agent-overlap gate — drop windows when agent is speaking
# ---------------------------------------------------------------------------

def test_agent_speaking_drops_window():
    enc = _make_encoder()
    eng = _make_engine()
    rw = RollingWindow(encoder=enc, engine=eng, sample_rate=SR,
                       window_s=3.0, hop_s=1.0)

    rw.set_agent_speaking(True)
    states = rw.push_pcm(_sine_pcm(WINDOW_N))
    # Window available but dropped because agent is speaking
    assert states == []
    assert eng._speech_elapsed == 0.0


def test_agent_gate_clears_on_false():
    enc = _make_encoder()
    eng = _make_engine()
    rw = RollingWindow(encoder=enc, engine=eng, sample_rate=SR,
                       window_s=3.0, hop_s=1.0)

    rw.set_agent_speaking(True)
    rw.push_pcm(_sine_pcm(WINDOW_N))  # dropped
    rw.set_agent_speaking(False)
    states = rw.push_pcm(_sine_pcm(HOP_N))  # one hop more → second window, NOT dropped
    assert len(states) == 1


# ---------------------------------------------------------------------------
# Test 4: backpressure — large burst produces ≤ expected capped output
# ---------------------------------------------------------------------------

def test_backpressure_limits_windows_on_large_burst():
    enc = _make_encoder()
    eng = _make_engine()
    rw = RollingWindow(encoder=enc, engine=eng, sample_rate=SR,
                       window_s=3.0, hop_s=1.0)

    # 6 seconds of PCM (96,000 samples): naive processing gives 4 windows ((6-3)/1 + 1).
    # Backpressure skips iteration 2 when buffer exceeds window_n + hop_n (64,000 samples),
    # yielding 3 windows: iter 1 [0:48k], skip, iter 3 [32k:80k], iter 4 [48k:96k].
    states = rw.push_pcm(_sine_pcm(6 * SR))
    assert len(states) == 3, f"Expected 3 windows (6s → 4 naive - 1 skip); got {len(states)}"


# ---------------------------------------------------------------------------
# Test 5: reset clears buffer and engine
# ---------------------------------------------------------------------------

def test_reset_clears_state():
    enc = _make_encoder()
    eng = _make_engine()
    rw = RollingWindow(encoder=enc, engine=eng, sample_rate=SR,
                       window_s=3.0, hop_s=1.0)

    rw.push_pcm(_sine_pcm(WINDOW_N))
    assert eng._speech_elapsed > 0.0
    rw.reset()
    assert eng._speech_elapsed == 0.0
    # Buffer should also be empty — next push needs WINDOW_N samples again
    states = rw.push_pcm(_sine_pcm(WINDOW_N - 1))
    assert states == []
