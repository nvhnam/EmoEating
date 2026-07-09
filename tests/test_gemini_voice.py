"""
Unit tests for app/services/gemini_voice.py
Run: pytest tests/test_gemini_voice.py -v
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from services import gemini_voice


def _mock_response(status_code=200, json_body=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body or {}
    resp.text = text
    return resp


@patch("services.gemini_voice.GEMINI_API_KEY", "test-key")
@patch("services.gemini_voice.requests.post")
def test_mint_ephemeral_token_success(mock_post):
    mock_post.return_value = _mock_response(200, {"name": "ephemeral-abc123"})
    result = gemini_voice.mint_ephemeral_token()
    assert result["client_secret"] == "ephemeral-abc123"
    assert result["model"] == gemini_voice.GEMINI_LIVE_MODEL
    assert result["voice"] == gemini_voice.GEMINI_VOICE
    assert result["ws_url"] == gemini_voice.GEMINI_WS_URL
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["params"] == {"key": "test-key"}


@patch("services.gemini_voice.GEMINI_API_KEY", "")
def test_mint_ephemeral_token_missing_key():
    try:
        gemini_voice.mint_ephemeral_token()
        assert False, "expected GeminiVoiceError"
    except gemini_voice.GeminiVoiceError as exc:
        assert "GEMINI_API_KEY" in str(exc)


@patch("services.gemini_voice.GEMINI_API_KEY", "test-key")
@patch("services.gemini_voice.requests.post")
def test_mint_ephemeral_token_non_200(mock_post):
    mock_post.return_value = _mock_response(503, {}, text="upstream unavailable")
    try:
        gemini_voice.mint_ephemeral_token()
        assert False, "expected GeminiVoiceError"
    except gemini_voice.GeminiVoiceError as exc:
        assert "503" in str(exc)


@patch("services.gemini_voice.GEMINI_API_KEY", "test-key")
@patch("services.gemini_voice.requests.post")
def test_mint_ephemeral_token_empty_token_field(mock_post):
    mock_post.return_value = _mock_response(200, {"name": ""})
    try:
        gemini_voice.mint_ephemeral_token()
        assert False, "expected GeminiVoiceError"
    except gemini_voice.GeminiVoiceError as exc:
        assert "empty token" in str(exc).lower()


@patch("services.gemini_voice.GEMINI_API_KEY", "test-key")
@patch("services.gemini_voice.requests.post")
def test_mint_ephemeral_token_transport_error(mock_post):
    import requests as requests_module
    mock_post.side_effect = requests_module.ConnectionError("network down")
    try:
        gemini_voice.mint_ephemeral_token()
        assert False, "expected GeminiVoiceError"
    except gemini_voice.GeminiVoiceError as exc:
        assert "unreachable" in str(exc).lower()


def test_is_configured_reflects_api_key():
    with patch("services.gemini_voice.GEMINI_API_KEY", ""):
        assert gemini_voice.is_configured() is False
    with patch("services.gemini_voice.GEMINI_API_KEY", "some-key"):
        assert gemini_voice.is_configured() is True
