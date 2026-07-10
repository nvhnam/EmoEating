"""
Standalone manual test harness for the voice_conversation component.

Not part of the app's page flow — renders the component in isolation with a
real minted Gemini ephemeral token, so the full live conversation (mic
permission, Gemini Live connection, agent-voice gate, PCM accumulation, WAV
encoding, setComponentValue round-trip) can be verified in a real browser
before wiring the component into app/pages/03_emotion.py.

Requires GEMINI_API_KEY set in .env.

Run:
    streamlit run scripts/dev_voice_component_harness.py
"""
from __future__ import annotations

import base64
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from components.voice_conversation import render_voice_conversation
from services.gemini_voice import GeminiVoiceError, is_configured, mint_ephemeral_token

st.set_page_config(page_title="Voice component harness")
st.title("Voice conversation component — manual test harness")
st.caption(
    "Click 'Start voice check-in', allow the microphone, have a short back-and-forth "
    "with the agent, then click 'Wrap up' (or wait for the target/timeout — set low "
    "here for faster manual testing)."
)

if not is_configured():
    st.error("GEMINI_API_KEY is not set in .env — add it to test the live conversation.")
    st.stop()

if "dev_harness_token" not in st.session_state:
    try:
        st.session_state["dev_harness_token"] = mint_ephemeral_token()
    except GeminiVoiceError as exc:
        st.error(f"Failed to mint ephemeral token: {exc}")
        st.stop()

token = st.session_state["dev_harness_token"]

result = render_voice_conversation(
    target_speech_s=20.0,
    timeout_s=45.0,
    client_secret=token["client_secret"],
    model=token["model"],
    voice=token["voice"],
    ws_url=token["ws_url"],
    key="dev_harness",
)

if result is not None:
    st.success(f"Component returned a result — {result['speech_elapsed_s']:.1f}s of speech collected.")
    audio_bytes = base64.b64decode(result["audio_b64"])
    st.write(f"Decoded WAV size: {len(audio_bytes)} bytes")
    st.audio(audio_bytes, format="audio/wav")

    if st.button("Classify with existing SER engine"):
        from engine.ser_engine import predict_zone_from_audio

        with st.spinner("Running predict_zone_from_audio..."):
            zone, probs = predict_zone_from_audio(audio_bytes)
        st.write("Zone:", zone)
        st.write("Probs:", probs)

    if st.button("Start a new conversation"):
        st.session_state.pop("dev_harness_token", None)
        st.rerun()
else:
    st.info("Waiting for the conversation to finish...")
