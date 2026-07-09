"""
Custom Streamlit component: live voice check-in.

Replaces the RAVDESS voice-read flow. The conversation itself (mic capture,
the Gemini Live WebSocket session, the agent-voice gate, and audio
accumulation) runs entirely client-side in main.js; this module only
declares the component and passes through the ephemeral-token/model config
minted by services/gemini_voice.py. The persona/system-instruction text is
defined once, directly in main.js — there is no server-side Gemini prompt to
keep in sync with, so it is not threaded through as a prop.
"""

from __future__ import annotations

import os

import streamlit.components.v1 as components

_COMPONENT_DIR = os.path.dirname(os.path.abspath(__file__))
_component_func = components.declare_component("voice_conversation", path=_COMPONENT_DIR)


def render_voice_conversation(
    *,
    target_speech_s: float,
    timeout_s: float,
    client_secret: str = "",
    model: str = "",
    voice: str = "",
    ws_url: str = "",
    key: str | None = None,
) -> dict | None:
    """
    Render the live voice check-in component.

    Returns None while the conversation is in progress, or
    ``{"audio_b64": str, "speech_elapsed_s": float}`` once the user finishes
    (target speech duration reached, timeout, or manual wrap-up).
    """
    return _component_func(
        target_speech_s=target_speech_s,
        timeout_s=timeout_s,
        client_secret=client_secret,
        model=model,
        voice=voice,
        ws_url=ws_url,
        key=key,
        default=None,
    )
