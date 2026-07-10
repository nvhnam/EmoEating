"""
Contract test for the live voice check-in feature.

Verifies that a WAV blob built the same way the voice_conversation component's
main.js builds one (44-byte RIFF/WAVE header + raw 16kHz mono 16-bit PCM) is
accepted by the EXISTING, unchanged predict_zone_from_audio() and produces a
zone/probs shape the recommendation pipeline can consume. This is the seam
where the new feature's client-side audio collection hands off to the
pre-existing (and unmodified) SER engine.

Requires the emotion2vec_plus_large backbone + CREMA-D probe to be available
(funasr/modelscope installed, model cached). Skipped otherwise.
Run: pytest tests/test_voice_panel_contract.py -v
"""
from __future__ import annotations

import io
import os
import struct
import sys
import wave

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from config import CREMA_LABEL_NAMES, ZONE_LABELS

pytest.importorskip("funasr", reason="FunASR not installed — SER unavailable")
pytest.importorskip("torch", reason="torch not installed — SER unavailable")

from engine.ser_engine import current_backend, is_available, predict_zone_from_audio

_CANONICAL_ZONES = set(ZONE_LABELS.keys())


def _synthetic_wav_bytes(duration_s: float = 3.0, sample_rate: int = 16000) -> bytes:
    """Build a WAV blob matching the component's encodeWav() output format."""
    t = np.linspace(0, duration_s, int(sample_rate * duration_s), endpoint=False)
    tone = (0.2 * np.sin(2 * np.pi * 220 * t) * 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(tone.tobytes())
    return buf.getvalue()


def test_synthetic_wav_matches_js_encoder_header_shape():
    """Sanity-check the WAV header shape matches what main.js's encodeWav() writes."""
    audio_bytes = _synthetic_wav_bytes(duration_s=1.0)
    assert audio_bytes[0:4] == b"RIFF"
    assert audio_bytes[8:12] == b"WAVE"
    assert audio_bytes[12:16] == b"fmt "
    channels = struct.unpack("<H", audio_bytes[22:24])[0]
    sample_rate = struct.unpack("<I", audio_bytes[24:28])[0]
    bits_per_sample = struct.unpack("<H", audio_bytes[34:36])[0]
    assert channels == 1
    assert sample_rate == 16000
    assert bits_per_sample == 16


@pytest.mark.skipif(not is_available(), reason="SER backend not available in this environment")
def test_predict_zone_from_audio_accepts_conversation_style_wav():
    """The existing, unmodified predict_zone_from_audio() must accept audio
    collected from the live conversation exactly as it accepts RAVDESS recordings."""
    audio_bytes = _synthetic_wav_bytes(duration_s=3.0)
    zone, probs = predict_zone_from_audio(audio_bytes)

    assert zone in _CANONICAL_ZONES, f"zone {zone!r} not in canonical set {_CANONICAL_ZONES}"

    backend = current_backend()
    if backend["id"] == "crema4class":
        assert set(probs.keys()) <= set(CREMA_LABEL_NAMES)
    assert abs(sum(probs.values()) - 1.0) < 1e-3
