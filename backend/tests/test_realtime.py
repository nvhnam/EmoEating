"""POST /api/realtime/token: ephemeral token returned, key never in response, rate cap."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from emoeating.config import Settings
from api.main import create_app

_KEY = "sk-test-REAL_KEY_NEVER_IN_RESPONSE"

REALTIME_SETTINGS = Settings(
    google_image_api_key=None,
    google_image_cx=None,
    google_places_api_key=None,
    emo_model_path=None,
    store_path=None,
    cors_origins=("http://localhost:5173",),
    openai_api_key=_KEY,
    openai_realtime_model="gpt-4o-realtime-preview",
    openai_realtime_voice="alloy",
    realtime_rate_per_user=2,
)

NO_KEY_SETTINGS = Settings(
    google_image_api_key=None,
    google_image_cx=None,
    google_places_api_key=None,
    emo_model_path=None,
    store_path=None,
    cors_origins=("http://localhost:5173",),
)

_GEMINI_KEY = "google-test-REAL_KEY_NEVER_IN_RESPONSE"

GEMINI_SETTINGS = Settings(
    google_image_api_key=None,
    google_image_cx=None,
    google_places_api_key=None,
    emo_model_path=None,
    store_path=None,
    cors_origins=("http://localhost:5173",),
    voice_provider="gemini",
    google_api_key=_GEMINI_KEY,
    realtime_rate_per_user=2,
)

GEMINI_NO_KEY_SETTINGS = Settings(
    google_image_api_key=None,
    google_image_cx=None,
    google_places_api_key=None,
    emo_model_path=None,
    store_path=None,
    cors_origins=("http://localhost:5173",),
    voice_provider="gemini",
    google_api_key=None,
)

BOGUS_PROVIDER_SETTINGS = Settings(
    google_image_api_key=None,
    google_image_cx=None,
    google_places_api_key=None,
    emo_model_path=None,
    store_path=None,
    cors_origins=("http://localhost:5173",),
    voice_provider="bogus",
    realtime_rate_per_user=2,
)

_FAKE_GEMINI_RESPONSE = {"name": "auth_tokens/eph-xyz"}


def _make_mock_gemini_httpx():
    """Returns a context-manager-compatible mock for httpx.AsyncClient (Gemini)."""
    fake_resp = httpx.Response(200, json=_FAKE_GEMINI_RESPONSE)
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=fake_resp)
    return mock_client

_FAKE_OPENAI_RESPONSE = {
    "client_secret": {"value": "ephemeral-tok-xyz"},
    "model": "gpt-4o-realtime-preview",
    "voice": "alloy",
}


def _make_mock_httpx():
    """Returns a context-manager-compatible mock for httpx.AsyncClient."""
    fake_resp = httpx.Response(200, json=_FAKE_OPENAI_RESPONSE)
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=fake_resp)
    return mock_client


@pytest.fixture
def realtime_app():
    app = create_app(REALTIME_SETTINGS)
    return app


@pytest.fixture
def realtime_client(realtime_app):
    return TestClient(realtime_app)


@pytest.fixture
def no_key_client():
    app = create_app(NO_KEY_SETTINGS)
    return TestClient(app)


@pytest.fixture
def gemini_app_client():
    app = create_app(GEMINI_SETTINGS)
    client = TestClient(app)
    return client, _GEMINI_KEY


@pytest.fixture
def gemini_app_no_key_client():
    app = create_app(GEMINI_NO_KEY_SETTINGS)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Test 1: ephemeral token returned
# ---------------------------------------------------------------------------

def test_token_returned(realtime_client):
    with patch("api.realtime.httpx.AsyncClient", return_value=_make_mock_httpx()):
        resp = realtime_client.post("/api/realtime/token")
    assert resp.status_code == 200
    body = resp.json()
    assert "client_secret" in body
    assert body["client_secret"] == "ephemeral-tok-xyz"
    assert body["model"] == "gpt-4o-realtime-preview"
    assert body["voice"] == "alloy"
    assert body["provider"] == "openai"


# ---------------------------------------------------------------------------
# Test 2: real API key must never appear in the response body
# ---------------------------------------------------------------------------

def test_real_key_never_in_response(realtime_client):
    with patch("api.realtime.httpx.AsyncClient", return_value=_make_mock_httpx()):
        resp = realtime_client.post("/api/realtime/token")
    assert resp.status_code == 200
    response_text = json.dumps(resp.json())
    assert _KEY not in response_text, (
        f"Real API key leaked into response body: {response_text!r}"
    )


# ---------------------------------------------------------------------------
# Test 3: rate cap → 429
# ---------------------------------------------------------------------------

def test_rate_cap_returns_429(realtime_client):
    # realtime_rate_per_user=2 → first two succeed, third is 429.
    with patch("api.realtime.httpx.AsyncClient", return_value=_make_mock_httpx()):
        r1 = realtime_client.post("/api/realtime/token")
        r2 = realtime_client.post("/api/realtime/token")
        r3 = realtime_client.post("/api/realtime/token")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429


# ---------------------------------------------------------------------------
# Test 4: 503 when OpenAI key not configured
# ---------------------------------------------------------------------------

def test_503_without_openai_key(no_key_client):
    resp = no_key_client.post("/api/realtime/token")
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Test 5: upstream OpenAI error → 502
# ---------------------------------------------------------------------------

def test_502_on_upstream_error(realtime_client):
    error_resp = httpx.Response(401, json={"error": "Unauthorized"})
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=error_resp)
    with patch("api.realtime.httpx.AsyncClient", return_value=mock_client):
        resp = realtime_client.post("/api/realtime/token")
    assert resp.status_code == 502


# ---------------------------------------------------------------------------
# Test 6: transport error (ConnectError) → 502, no stack trace or API key
# ---------------------------------------------------------------------------

def test_502_on_transport_error(realtime_client):
    """httpx.ConnectError must map to 502, not 500, with no key in body."""
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
    with patch("api.realtime.httpx.AsyncClient", return_value=mock_client):
        resp = realtime_client.post("/api/realtime/token")
    assert resp.status_code == 502
    body_text = json.dumps(resp.json())
    assert _KEY not in body_text, f"API key leaked in transport-error response: {body_text!r}"
    assert "Traceback" not in body_text, "Stack trace leaked in transport-error response"


# ---------------------------------------------------------------------------
# Test 7: empty/missing client_secret.value from OpenAI → 502
# ---------------------------------------------------------------------------

def test_502_on_empty_secret(realtime_client):
    """Mocked 200 with no client_secret.value must return 502, not 200 with empty secret."""
    empty_resp = httpx.Response(200, json={"client_secret": {"value": ""}, "model": "x", "voice": "y"})
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=empty_resp)
    with patch("api.realtime.httpx.AsyncClient", return_value=mock_client):
        resp = realtime_client.post("/api/realtime/token")
    assert resp.status_code == 502
    assert "Empty secret" in resp.json().get("detail", "")


# ---------------------------------------------------------------------------
# Test 8: Gemini provider — ephemeral token returned, real google key hidden
# ---------------------------------------------------------------------------

def test_gemini_token_returns_ephemeral_and_hides_real_key(gemini_app_client):
    client, real_key = gemini_app_client
    with patch("api.realtime.httpx.AsyncClient", return_value=_make_mock_gemini_httpx()):
        resp = client.post("/api/realtime/token")
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "gemini"
    assert body["client_secret"]               # the ephemeral token
    assert body["api_version"] == "v1alpha"
    assert body["ws_url"].startswith("wss://")
    # the REAL google key must never appear in the response
    assert real_key not in json.dumps(body)


# ---------------------------------------------------------------------------
# Test 9: 503 when the ACTIVE provider's key is missing (gemini)
# ---------------------------------------------------------------------------

def test_token_503_when_active_provider_key_missing(gemini_app_no_key_client):
    resp = gemini_app_no_key_client.post("/api/realtime/token")
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Test 10: /api/voice/config reports the active provider
# ---------------------------------------------------------------------------

def test_voice_config_reports_active_provider(gemini_app_client):
    client, _ = gemini_app_client
    body = client.get("/api/voice/config").json()
    assert body == {"provider": "gemini", "provider_name": "Google Gemini"}


# ---------------------------------------------------------------------------
# Test 11: unknown/misconfigured provider → 500 (spec §6.4, never silent OpenAI)
# ---------------------------------------------------------------------------

def test_unknown_provider_returns_500():
    client = TestClient(create_app(BOGUS_PROVIDER_SETTINGS))
    resp = client.post("/api/realtime/token")
    assert resp.status_code == 500
    assert "misconfigured" in resp.json().get("detail", "")
