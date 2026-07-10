"""
Gemini Live ephemeral token minting for the live voice check-in.

The live conversation itself (mic capture, Gemini Live WebSocket, agent-voice
gate, audio accumulation) runs entirely client-side in a custom Streamlit
component — see app/components/voice_conversation/. The one piece that must
stay server-side is swapping the real GEMINI_API_KEY for a short-lived
ephemeral token, since the real key must never reach the browser.
"""

from __future__ import annotations

import requests

from config import GEMINI_API_KEY, GEMINI_AUTH_TOKENS_URL, GEMINI_LIVE_MODEL, GEMINI_VOICE, GEMINI_WS_URL


class GeminiVoiceError(RuntimeError):
    """Raised when an ephemeral token cannot be minted."""


def is_configured() -> bool:
    """Return True if a Gemini API key is present in the environment."""
    return bool(GEMINI_API_KEY)


def mint_ephemeral_token() -> dict:
    """
    Swap the real GEMINI_API_KEY for a short-lived ephemeral token the browser
    can use to open a Gemini Live WebSocket session directly.

    Returns:
        {"client_secret": str, "model": str, "voice": str, "ws_url": str}

    Raises:
        GeminiVoiceError — missing API key, transport failure, non-200
        response, or an empty token in the response.
    """
    if not GEMINI_API_KEY:
        raise GeminiVoiceError(
            "GEMINI_API_KEY is not set. Add it to your .env file to enable "
            "the voice check-in."
        )

    try:
        resp = requests.post(
            GEMINI_AUTH_TOKENS_URL,
            params={"key": GEMINI_API_KEY},
            json={},
            timeout=10.0,
        )
    except requests.RequestException as exc:
        raise GeminiVoiceError(f"Gemini token endpoint unreachable: {exc}") from exc

    if resp.status_code != 200:
        raise GeminiVoiceError(
            f"Gemini token mint failed (HTTP {resp.status_code}): {resp.text[:200]}"
        )

    data = resp.json()
    token = data.get("name", "")
    if not token:
        raise GeminiVoiceError("Gemini token endpoint returned an empty token.")

    return {
        "client_secret": token,
        "model": GEMINI_LIVE_MODEL,
        "voice": GEMINI_VOICE,
        "ws_url": GEMINI_WS_URL,
    }
