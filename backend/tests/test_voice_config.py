# backend/tests/test_voice_config.py
import importlib
import os
from unittest.mock import patch

import dotenv as _dotenv

from emoeating import config

# Capture the genuine loader at import time, before the autouse _no_dotenv fixture
# (conftest.py) patches it — the .env-loading test below restores it deliberately.
_REAL_LOAD_DOTENV = _dotenv.load_dotenv


def _reload_settings(monkeypatch, **env):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import emoeating.config as cfg
    importlib.reload(cfg)
    return cfg.load_settings()


def test_voice_provider_defaults_to_openai(monkeypatch):
    monkeypatch.delenv("EMOEATING_VOICE_PROVIDER", raising=False)
    s = _reload_settings(monkeypatch)
    assert s.voice_provider == "openai"
    assert s.gemini_live_model == "gemini-3.1-flash-live-preview"


def test_voice_provider_and_gemini_keys_from_env(monkeypatch):
    s = _reload_settings(
        monkeypatch,
        EMOEATING_VOICE_PROVIDER="gemini",
        EMOEATING_GOOGLE_API_KEY="g-secret",
        # Non-default sentinels so these actually prove the env var is read.
        EMOEATING_GEMINI_VOICE="Charon",
        EMOEATING_GEMINI_LIVE_MODEL="gemini-test-model",
    )
    assert s.voice_provider == "gemini"
    assert s.google_api_key == "g-secret"
    assert s.gemini_voice == "Charon"
    assert s.gemini_live_model == "gemini-test-model"
    assert s.gemini_ws_url.startswith("wss://")


def test_dotenv_is_loaded_and_real_env_overrides(monkeypatch, tmp_path):
    # Restore the real loader (the autouse fixture neutralizes it for other tests).
    monkeypatch.setattr("dotenv.load_dotenv", _REAL_LOAD_DOTENV)
    # A local .env supplies a value when no real env var is set...
    (tmp_path / ".env").write_text("EMOEATING_GEMINI_VOICE=FromDotEnv\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("EMOEATING_GEMINI_VOICE", raising=False)
    import emoeating.config as cfg
    importlib.reload(cfg)
    assert cfg.load_settings().gemini_voice == "FromDotEnv"
    # ...but a real environment variable takes precedence over the .env value.
    monkeypatch.setenv("EMOEATING_GEMINI_VOICE", "FromRealEnv")
    assert cfg.load_settings().gemini_voice == "FromRealEnv"


def test_confidence_engine_knobs_present():
    assert config.WINDOW_S == 3.0
    assert config.HOP_S == 1.0
    assert config.EMA_ALPHA == 0.3
    assert config.MIN_WINDOW_CONF == 0.35
    assert config.SPEECH_FLOOR_S == 18.0
    assert config.STABILITY_N == 5
    assert config.MARGIN_THETA == 0.15
    assert config.TIMEOUT_S == 90.0
    assert config.SAFETY_NEG_THRESHOLD == 0.8
    assert config.MAX_CONCURRENT_WS_SESSIONS == 10


def test_emotion_zone_covers_all_nine_labels():
    valid_zones = {"POS_ACTIVE", "NEG_ACTIVE", "NEG_DEACTIVE", "NEUTRAL_CALM"}
    assert set(config.EMOTION_ZONE) == set(config.EMOTION_VA)
    for label, zone in config.EMOTION_ZONE.items():
        assert zone in valid_zones, f"{label} mapped to unknown zone {zone!r}"


def test_emotion_zone_specific_mappings():
    """Key placements derived from EMOTION_VA + zone thresholds."""
    assert config.EMOTION_ZONE["happy"] == "POS_ACTIVE"
    assert config.EMOTION_ZONE["angry"] == "NEG_ACTIVE"
    assert config.EMOTION_ZONE["sad"] == "NEG_DEACTIVE"
    assert config.EMOTION_ZONE["neutral"] == "NEUTRAL_CALM"
    assert config.EMOTION_ZONE["other"] == "NEUTRAL_CALM"
    assert config.EMOTION_ZONE["unknown"] == "NEUTRAL_CALM"


def test_settings_has_openai_fields():
    from emoeating.config import Settings
    s = Settings(
        google_image_api_key=None,
        google_image_cx=None,
        google_places_api_key=None,
        emo_model_path=None,
        store_path=None,
        cors_origins=("http://localhost:5173",),
    )
    assert s.openai_api_key is None
    assert s.openai_realtime_model == "gpt-4o-realtime-preview"
    assert s.openai_realtime_voice == "alloy"
    assert s.realtime_rate_per_user == 5


def test_load_settings_reads_openai_env_vars():
    from emoeating.config import load_settings
    env = {
        "EMOEATING_OPENAI_API_KEY": "sk-test-abc",
        "EMOEATING_OPENAI_REALTIME_MODEL": "gpt-4o-mini-realtime",
        "EMOEATING_OPENAI_REALTIME_VOICE": "shimmer",
        "EMOEATING_REALTIME_RATE_PER_USER": "3",
    }
    with patch.dict(os.environ, env):
        s = load_settings()
    assert s.openai_api_key == "sk-test-abc"
    assert s.openai_realtime_model == "gpt-4o-mini-realtime"
    assert s.openai_realtime_voice == "shimmer"
    assert s.realtime_rate_per_user == 3
