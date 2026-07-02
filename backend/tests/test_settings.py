# backend/tests/test_settings.py
from emoeating.config import Settings, load_settings


def test_defaults_when_env_absent(monkeypatch):
    for k in (
        "EMOEATING_GOOGLE_IMAGE_API_KEY", "EMOEATING_GOOGLE_IMAGE_CX",
        "EMOEATING_GOOGLE_PLACES_API_KEY", "EMOEATING_MODEL_PATH",
        "EMOEATING_STORE_PATH", "EMOEATING_CORS_ORIGINS",
    ):
        monkeypatch.delenv(k, raising=False)
    s = load_settings()
    assert isinstance(s, Settings)
    assert s.google_image_api_key is None
    assert s.google_places_api_key is None
    assert s.emo_model_path is None
    assert s.store_path is None
    assert s.cors_origins == ("http://localhost:5173",)


def test_reads_keys_and_splits_origins(monkeypatch):
    monkeypatch.setenv("EMOEATING_GOOGLE_IMAGE_API_KEY", "img-key")
    monkeypatch.setenv("EMOEATING_GOOGLE_IMAGE_CX", "cx-id")
    monkeypatch.setenv("EMOEATING_GOOGLE_PLACES_API_KEY", "places-key")
    monkeypatch.setenv("EMOEATING_MODEL_PATH", "/models/e2v")
    monkeypatch.setenv("EMOEATING_CORS_ORIGINS", "http://a, http://b")
    s = load_settings()
    assert s.google_image_api_key == "img-key"
    assert s.google_image_cx == "cx-id"
    assert s.google_places_api_key == "places-key"
    assert s.emo_model_path == "/models/e2v"
    assert s.cors_origins == ("http://a", "http://b")  # trimmed
