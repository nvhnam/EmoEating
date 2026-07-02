"""App wiring: routes registered, DI seams work, funasr not imported at startup."""
import sys

import pytest
from fastapi.testclient import TestClient

from emoeating.config import Settings
from emoeating.external.images import NullImageProvider, GoogleImageProvider
from emoeating.external.restaurants import NullRestaurantProvider, GooglePlacesProvider
from emoeating.ser.encoder import MockEncoder
from api.main import build_image_provider, build_restaurant_provider, build_store, create_app
from api import routes


def _settings(**over):
    base = dict(google_image_api_key=None, google_image_cx=None,
                google_places_api_key=None, emo_model_path=None,
                store_path=None, cors_origins=("http://localhost:5173",))
    base.update(over)
    return Settings(**base)


TEST_SETTINGS = Settings(
    google_image_api_key=None,
    google_image_cx=None,
    google_places_api_key=None,
    emo_model_path=None,
    store_path=None,
    cors_origins=("http://localhost:5173",),
)


@pytest.fixture
def app():
    return create_app(TEST_SETTINGS)


@pytest.fixture
def client(app):
    return TestClient(app)


# ---------------------------------------------------------------------------
# Existing wiring / provider tests (pre-voice)
# ---------------------------------------------------------------------------

def test_image_provider_selection():
    assert isinstance(build_image_provider(_settings()), NullImageProvider)
    real = build_image_provider(_settings(google_image_api_key="k", google_image_cx="c"))
    assert isinstance(real, GoogleImageProvider)
    # one half of the pair missing -> still Null
    assert isinstance(build_image_provider(_settings(google_image_api_key="k")), NullImageProvider)


def test_restaurant_provider_selection():
    assert isinstance(build_restaurant_provider(_settings()), NullRestaurantProvider)
    real = build_restaurant_provider(_settings(google_places_api_key="k"))
    assert isinstance(real, GooglePlacesProvider)


def test_cors_preflight_allows_sveltekit_origin(client):
    r = client.options(
        "/api/images",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_build_store_returns_none_when_store_path_not_set():
    """build_store must return None (not an empty :memory: FoodStore) when store_path is absent."""
    assert build_store(_settings()) is None


def test_recommend_returns_503_when_store_is_none():
    """POST /api/recommend must return 503 when get_store is overridden to yield None."""
    app = create_app(_settings())
    app.dependency_overrides[routes.get_store] = lambda: None
    c = TestClient(app)
    r = c.post("/api/recommend", json={"zone": "NEG_DEACTIVE"})
    assert r.status_code == 503
    assert "food store" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Task 6: voice-agent route registration and state initialisation
# ---------------------------------------------------------------------------

def _all_route_paths(app) -> list[str]:
    """Collect paths from all registered routes, including from included routers.

    Starlette 1.3+ stores included routers as _IncludedRouter (no .path), so
    we recurse into original_router.routes to collect the actual paths.
    """
    paths: list[str] = []
    for r in app.routes:
        if hasattr(r, "path"):
            paths.append(r.path)
        elif hasattr(r, "original_router") and hasattr(r.original_router, "routes"):
            for sub in r.original_router.routes:
                if hasattr(sub, "path"):
                    paths.append(sub.path)
    return paths


def test_ws_emotion_route_registered(app):
    route_paths = _all_route_paths(app)
    assert "/ws/emotion" in route_paths, (
        f"/ws/emotion not found. Routes: {route_paths}"
    )


def test_realtime_token_route_registered(app):
    route_paths = _all_route_paths(app)
    assert "/api/realtime/token" in route_paths, (
        f"/api/realtime/token not found. Routes: {route_paths}"
    )


def test_app_state_has_ws_session_tracking():
    app = create_app(TEST_SETTINGS)
    assert hasattr(app.state, "active_ws_sessions")
    assert app.state.active_ws_sessions == 0
    assert hasattr(app.state, "max_ws_sessions")
    assert hasattr(app.state, "realtime_rate_log")
    assert isinstance(app.state.realtime_rate_log, dict)


def test_funasr_not_imported_at_startup():
    # funasr is imported only inside Emotion2VecEncoder._get_model(), never at module load.
    assert "funasr" not in sys.modules, (
        "funasr was imported at module-load time — heavy import must stay lazy"
    )


def test_infer_route_removed(client):
    """The one-shot /api/infer path is gone: /ws/emotion is the only way into SER."""
    assert "/api/infer" not in _all_route_paths(client.app)


def test_ws_emotion_reachable_with_mock_encoder():
    """Integration: WS endpoint reachable, returns at least one tick."""
    import numpy as np
    from emoeating.voice.confidence import ConfidenceEngine

    app = create_app(TEST_SETTINGS)
    app.state.encoder = MockEncoder({"sad": 0.8, "neutral": 0.15, "other": 0.05})
    app.state.create_engine = lambda: ConfidenceEngine(
        speech_floor_s=2.0, stability_n=2, margin_theta=0.05, timeout_s=9999.0
    )
    client = TestClient(app)

    t = np.arange(4 * 16000, dtype=np.float32)
    pcm = (4000 * np.sin(2 * np.pi * 440 * t / 16000)).astype(np.int16).tobytes()

    with client.websocket_connect("/ws/emotion") as ws:
        ws.send_bytes(pcm)
        got_tick = False
        for _ in range(20):
            try:
                msg = ws.receive_json()
                if msg.get("type") == "tick":
                    got_tick = True
                if msg.get("type") == "done":
                    break
            except Exception:
                break
    assert got_tick
