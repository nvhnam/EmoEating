"""POST /api/realtime/token — mints an OpenAI Realtime ephemeral session secret.

IMPORTANT — verify before deploying:
The OpenAI Realtime API is in beta. Before going live, confirm:
  • Endpoint: currently assumed POST https://api.openai.com/v1/realtime/sessions
  • Request body fields (model, voice, instructions, modalities, etc.)
  • Response field path for the ephemeral token (currently client_secret.value)
  • Whether the endpoint path has changed to /v1/realtime or /v1/realtime/client_secrets
Reference: https://platform.openai.com/docs/api-reference/realtime
"""
from __future__ import annotations

import time

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

realtime_router = APIRouter()

# ---------------------------------------------------------------------------
# Agent system prompt (elicitation per spec §6)
# Keep the safety guardrails in sync with backend _AGENT_INSTRUCTIONS (realtime.py)
# / frontend SYSTEM_INSTRUCTION (gemini.ts): 988 Lifeline, no-diagnosis, no-food.
# ---------------------------------------------------------------------------
_AGENT_INSTRUCTIONS = (
    "You are the friendly check-in host inside EmoEating, a food app that suggests meals "
    "matching how the user feels — read from the sound of their voice, never from their "
    "words. The user has just opened the menu; this short chat is what personalizes it. "
    "Your goal: get them talking warmly and naturally for about a minute so the app can "
    "hear how they are doing. Open the conversation yourself: one brief, warm greeting "
    "plus one easy question about their day — do not wait for them to speak first. Then "
    "follow their lead, one short open question at a time: their day, their energy right "
    "now, what has been on their mind, or something they are looking forward to. Keep "
    "your own turns to one or two sentences; they should do most of the talking, so "
    "invite them to say more. Never discuss, suggest, or ask about food, meals, hunger, "
    "or nutrition — the menu handles that after this chat. You are not a therapist and "
    "never diagnose. If they mention crisis or serious distress, acknowledge warmly, "
    "offer the 988 Suicide & Crisis Lifeline, and end gently. When told to wrap up, "
    "give one brief warm closing and stop talking."
)

# ---------------------------------------------------------------------------
# NOTE: Verify this endpoint path against current OpenAI docs before deploying.
# ---------------------------------------------------------------------------
_OPENAI_SESSIONS_URL = "https://api.openai.com/v1/realtime/sessions"

_RATE_WINDOW_S = 3600.0  # 1-hour sliding window for per-IP rate cap


class TokenResponse(BaseModel):
    provider: str
    client_secret: str
    model: str
    voice: str
    ws_url: str | None = None
    api_version: str | None = None


_PROVIDER_NAMES = {"openai": "OpenAI", "gemini": "Google Gemini"}

# Gemini Live ephemeral-token create endpoint (v1alpha). VERIFY against current docs.
_GEMINI_AUTH_TOKENS_URL = (
    "https://generativelanguage.googleapis.com/v1alpha/auth_tokens"
)


async def _mint_gemini_token(api_key: str) -> str:
    """Isolated Gemini call — mock in tests; VERIFY endpoint/shape in prod.

    Swaps the real GOOGLE_API_KEY for a short-lived ephemeral token. Returns the
    token string. Raises HTTPException(502) on any upstream/transport failure.
    """
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                _GEMINI_AUTH_TOKENS_URL,
                params={"key": api_key},
                json={},  # default token; lock-to-config can be added later
                timeout=10.0,
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="Gemini unreachable") from exc
    if resp.status_code != 200:
        raise HTTPException(
            status_code=502, detail=f"Gemini token mint failed ({resp.status_code})"
        )
    data = resp.json()
    token = data.get("name", "")  # VERIFY field path against current docs
    if not token:
        raise HTTPException(status_code=502, detail="Empty token from Gemini")
    return token


async def _mint_token(api_key: str, model: str, voice: str) -> str:
    """Isolated OpenAI call — mock this in tests; verify endpoint shape in prod.

    Returns the ephemeral token string (client_secret.value).
    Raises HTTPException(502) on any upstream failure or transport error.
    """
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                _OPENAI_SESSIONS_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "voice": voice,
                    "instructions": _AGENT_INSTRUCTIONS,
                },
                timeout=10.0,
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="OpenAI unreachable") from exc
    if resp.status_code != 200:
        raise HTTPException(
            status_code=502, detail=f"OpenAI token mint failed ({resp.status_code})"
        )
    data = resp.json()
    # NOTE: field path may change — verify against current docs.
    secret = data.get("client_secret", {})
    if isinstance(secret, dict):
        token = secret.get("value", "")
    else:
        token = str(secret)
    if not token:
        raise HTTPException(status_code=502, detail="Empty secret from OpenAI")
    return token


def _enforce_rate_cap(log: dict, identifier: str, limit: int) -> None:
    """Sliding-window rate cap. Mutates log in place. Raises 429 if exceeded."""
    now = time.monotonic()
    cutoff = now - _RATE_WINDOW_S
    timestamps: list[float] = log.get(identifier, [])
    # Prune old entries.
    timestamps = [t for t in timestamps if t >= cutoff]
    if len(timestamps) >= limit:
        log[identifier] = timestamps
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    timestamps.append(now)
    log[identifier] = timestamps


@realtime_router.post("/api/realtime/token", response_model=TokenResponse)
async def realtime_token(request: Request) -> TokenResponse:
    settings = request.app.state.settings
    provider = settings.voice_provider

    # Spec §6.4: an unknown/misconfigured provider must error loudly, never
    # silently fall through to the OpenAI path below.
    if provider not in ("openai", "gemini"):
        raise HTTPException(status_code=500, detail="voice provider misconfigured")

    # 503 if the ACTIVE provider's key is missing.
    if provider == "openai" and not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OpenAI not configured")
    if provider == "gemini" and not settings.google_api_key:
        raise HTTPException(status_code=503, detail="Gemini not configured")

    # Per-IP rate cap — lazily initialize on app.state so it persists across requests.
    if not hasattr(request.app.state, "realtime_rate_log"):
        request.app.state.realtime_rate_log = {}
    rate_log: dict = request.app.state.realtime_rate_log
    identifier = request.client.host if request.client else "unknown"
    _enforce_rate_cap(rate_log, identifier, settings.realtime_rate_per_user)

    if provider == "gemini":
        token = await _mint_gemini_token(settings.google_api_key)
        return TokenResponse(
            provider="gemini",
            client_secret=token,
            model=settings.gemini_live_model,
            voice=settings.gemini_voice,
            ws_url=settings.gemini_ws_url,
            api_version="v1alpha",
        )

    secret = await _mint_token(
        api_key=settings.openai_api_key,
        model=settings.openai_realtime_model,
        voice=settings.openai_realtime_voice,
    )
    return TokenResponse(
        provider="openai",
        client_secret=secret,
        model=settings.openai_realtime_model,
        voice=settings.openai_realtime_voice,
    )


@realtime_router.get("/api/voice/config")
async def voice_config(request: Request) -> dict:
    provider = request.app.state.settings.voice_provider
    return {"provider": provider, "provider_name": _PROVIDER_NAMES.get(provider, provider)}
