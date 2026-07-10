"""
Page 3 — Emotion Detection.

Two input paths (guide.md Phase 1 & 6):
  A. Manual: 11-emotion grid → VA coordinates → zone classification
  B. Voice:  live ~1 minute conversation with a Gemini voice agent collects
             user-only audio (agent's own speech excluded via a client-side
             playback gate — see components/voice_conversation), then a
             single batch call to emotion2vec_plus_large (FunASR) classifies
             the full collected audio → per-zone probability mass →
             max-mass zone (bypasses VA step). Classification itself is
             unchanged from the previous RAVDESS-read flow.

Russell Circumplex visualisation shown for both paths.
"""

from __future__ import annotations

import base64
import streamlit as st
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from components.emotion_selector import render_emotion_selector
from components.circumplex_plot import render_circumplex
from components.voice_conversation import render_voice_conversation
from engine.affect_mapper import emotion_to_va
from engine.zone_classifier import classify_zone
from config import ZONE_LABELS, ZONE_PALETTE, EMOTION_COORDS, VOICE_TARGET_SPEECH_S, VOICE_TIMEOUT_S
from utils.icons import icon, emotion_icon


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clear_reco_cache() -> None:
    """Evict all recommendation caches when emotion / zone changes."""
    st.session_state.pop("recommendations", None)
    st.session_state.pop("_reco_emotion", None)
    st.session_state.pop("session_id", None)
    for _k in [k for k in st.session_state
               if k.startswith(("food_images_", "restaurants_"))]:
        del st.session_state[_k]


def _render_zone_badge(zone: str, V: float | None = None, A: float | None = None) -> str:
    """Return HTML for a coloured zone badge, optionally with VA coords."""
    zone_label = ZONE_LABELS.get(zone, zone)
    ramp = ZONE_PALETTE.get(zone, ZONE_PALETTE["NEUTRAL_BASELINE"])
    va_html = ""
    if V is not None and A is not None:
        va_html = (
            f'<div style="font-size:0.85rem; color:var(--muted); margin-top:6px;">'
            f'Valence: <b>{V:+.2f}</b> &nbsp; Arousal: <b>{A:+.2f}</b></div>'
        )
    return (
        f'<div style="margin-top:10px;">'
        f'<span style="background:{ramp["tint"]}; color:{ramp["core"]}; '
        f'border:1px solid {ramp["core"]}; font-size:11px; font-weight:700; '
        f'padding:3px 10px; border-radius:var(--radius-pill);">Zone: {zone_label}</span>'
        f'</div>'
        f'{va_html}'
    )


# ── SER voice panel ───────────────────────────────────────────────────────────

def _render_voice_panel() -> None:
    """
    Voice emotion detection panel — live conversation with a Gemini agent.
    Supports two swappable classification backends:
      - crema4class: emotion2vec + CREMA-D linear probe (4-class, default)
      - original:    emotion2vec_plus_large 9-class off-the-shelf
    The conversation only collects user-only audio; classification is a
    single batch call to the existing predict_zone_from_audio(), unchanged
    from the previous RAVDESS-read flow. Renders inside an expander. Updates
    session state on confirmed use.
    """
    from engine.ser_engine import (
        is_available as ser_available,
        current_backend,
        set_backend,
    )
    from services.gemini_voice import GeminiVoiceError, is_configured, mint_ephemeral_token

    # ── Backend selector (runtime switch; no restart needed) ──────────────────
    _BACKEND_OPTIONS = {
        "crema4class": "CREMA-D probe — 4-class",
        "original":    "Original 9-class (emotion2vec_plus_large off-the-shelf)",
    }
    _cur_id = current_backend()["id"]
    selected_id = st.selectbox(
        "SER Backend",
        options=list(_BACKEND_OPTIONS.keys()),
        index=list(_BACKEND_OPTIONS.keys()).index(_cur_id),
        format_func=lambda k: _BACKEND_OPTIONS[k],
        key="ser_backend_selector",
        help="Switch between SER backends without restarting. "
             "CREMA-D probe is the Phase 7 upgrade (higher valence CCC); "
             "Original is the Phase 1 baseline.",
        label_visibility="collapsed",
    )
    if selected_id != _cur_id:
        set_backend(selected_id)
        # Clear any pending SER result from the previous backend
        for k in ("_ser_zone_pending", "_ser_probs_pending", "_ser_top_emotion"):
            st.session_state.pop(k, None)

    backend = current_backend()

    with st.expander(
        f"Voice Emotion Detection — {backend['label']}",
        icon=":material/mic:",
        expanded=False,
    ):
        st.caption(
            "Have a short, natural ~1 minute chat with a voice agent about your day. "
            "Nothing to read or rehearse — just talk. Only your voice is analysed; "
            "the agent's own responses never reach the emotion model."
        )

        if not ser_available():
            st.warning(
                "SER module not installed. "
                "Run `pip install funasr modelscope` and restart to enable voice detection.",
                icon=":material/warning:",
            )
        elif not is_configured():
            st.warning(
                "Voice check-in is not configured. Add `GEMINI_API_KEY` to your `.env` "
                "file to enable the live conversation.",
                icon=":material/warning:",
            )
        elif "_ser_zone_pending" not in st.session_state:
            # ── Conversation phase ───────────────────────────────────────────
            if "_voice_component_seq" not in st.session_state:
                st.session_state["_voice_component_seq"] = 0

            if "_voice_token" not in st.session_state:
                try:
                    st.session_state["_voice_token"] = mint_ephemeral_token()
                except GeminiVoiceError as exc:
                    st.error(f"Could not start the voice check-in: {exc}")

            token = st.session_state.get("_voice_token")
            if token is not None:
                result = render_voice_conversation(
                    target_speech_s=VOICE_TARGET_SPEECH_S,
                    timeout_s=VOICE_TIMEOUT_S,
                    client_secret=token["client_secret"],
                    model=token["model"],
                    voice=token["voice"],
                    ws_url=token["ws_url"],
                    key=f"voice_conv_{st.session_state['_voice_component_seq']}",
                )

                if result is not None:
                    # ── Analysis phase ───────────────────────────────────────
                    # The conversation collected user-only audio; classification
                    # is the SAME single batch call the RAVDESS flow used.
                    with st.spinner(f"Analysing emotion via {backend['label']}..."):
                        try:
                            from engine.ser_engine import predict_zone_from_audio
                            audio_bytes = base64.b64decode(result["audio_b64"])
                            zone, probs = predict_zone_from_audio(audio_bytes)
                            sorted_probs = sorted(probs.items(), key=lambda x: x[1], reverse=True)
                            st.session_state["_ser_zone_pending"] = zone
                            st.session_state["_ser_probs_pending"] = probs
                            st.session_state["_ser_top_emotion"] = sorted_probs[0][0]
                            st.session_state.pop("_voice_token", None)
                            st.rerun()
                        except ImportError as exc:
                            st.warning(f"SER not available: {str(exc)[:120]}")
                        except RuntimeError as exc:
                            st.error(
                                f"Voice analysis failed — try redoing the conversation. "
                                f"Details: {str(exc)[:200]}"
                            )

        # ── Display phase ────────────────────────────────────────────────────
        # Always renders from cached session state — no model call here.
        if "_ser_zone_pending" in st.session_state:
            zone = st.session_state["_ser_zone_pending"]
            probs = st.session_state["_ser_probs_pending"]
            sorted_probs = sorted(probs.items(), key=lambda x: x[1], reverse=True)

            st.markdown(f"**{backend['n_classes']}-class emotion probabilities:**")
            for emo, prob in sorted_probs:
                st.progress(
                    min(prob, 1.0),
                    text=f"{emo.capitalize()}: {prob:.1%}",
                )

            ramp = ZONE_PALETTE.get(zone, ZONE_PALETTE["NEUTRAL_BASELINE"])
            zone_label = ZONE_LABELS.get(zone, zone)
            st.markdown(
                f'<div style="margin-top:12px; padding:10px; '
                f'background:{ramp["tint"]}; border:1px solid {ramp["core"]}; '
                f'border-radius:var(--radius-md);">'
                f'<span style="font-size:12px; font-weight:700; color:{ramp["core"]};">'
                f'Detected Zone: {zone_label}</span>'
                f'<div style="font-size:11px; color:var(--muted); margin-top:4px;">'
                f'Top emotion: {sorted_probs[0][0].capitalize()} '
                f'({sorted_probs[0][1]:.1%} confidence)</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Post-hoc supportive note — additive only; classification already
            # happened, this never blocks or replaces the normal result.
            if zone in ("Q2_NEG_ACT", "Q3_NEG_DEACT") and sorted_probs[0][1] >= 0.4:
                st.info(
                    "If you're going through a hard time, you're not alone — the "
                    "988 Suicide & Crisis Lifeline (call or text **988**, US) is "
                    "available 24/7.",
                    icon=":material/favorite:",
                )

            st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

            col_confirm, col_discard = st.columns(2)
            with col_confirm:
                if st.button("Use voice result", type="primary", key="confirm_ser"):
                    _clear_reco_cache()
                    top_emo = st.session_state.pop("_ser_top_emotion", "neutral")
                    _zone_fallback = {
                        "Q1_POS_ACT": "happy",
                        "Q2_NEG_ACT": "stressed",
                        "Q3_NEG_DEACT": "tired",
                        "NEUTRAL_BASELINE": "neutral",
                    }
                    display_emotion = (
                        top_emo
                        if top_emo in EMOTION_COORDS
                        else _zone_fallback.get(zone, "neutral")
                    )
                    st.session_state["detected_emotion"] = display_emotion
                    st.session_state["ser_zone"]  = st.session_state.pop("_ser_zone_pending", zone)
                    st.session_state["ser_probs"] = st.session_state.pop("_ser_probs_pending", probs)
                    st.session_state["_voice_component_seq"] += 1
                    st.rerun()
            with col_discard:
                if st.button("Redo conversation", key="discard_ser"):
                    for k in ("_ser_zone_pending", "_ser_probs_pending", "_ser_top_emotion", "_voice_token"):
                        st.session_state.pop(k, None)
                    st.session_state["_voice_component_seq"] += 1
                    st.rerun()

        # Show current SER-assigned zone if active
        if st.session_state.get("ser_zone"):
            sz = st.session_state["ser_zone"]
            st.success(
                f"Voice zone active: **{ZONE_LABELS.get(sz, sz)}** — "
                "this overrides zone classification for recommendations.",
                icon=":material/check_circle:",
            )
            if st.button("Clear voice result", key="clear_ser"):
                for k in ("ser_zone", "ser_probs"):
                    st.session_state.pop(k, None)
                _clear_reco_cache()
                st.rerun()


# ── Main page ─────────────────────────────────────────────────────────────────

def show():
    st.title("How are you feeling right now?")
    st.markdown(
        "Your emotional state guides which nutrients your body may benefit from. "
        "Select your emotion below, or record your voice for automatic detection."
    )

    _render_voice_panel()

    st.divider()
    st.markdown("**Select your emotion:**")

    _prev_emotion = st.session_state.get("detected_emotion")  # snapshot before component writes
    newly_selected = render_emotion_selector(selected=_prev_emotion)
    if newly_selected:
        # Manual selection clears any prior SER zone; compare against pre-component snapshot
        if newly_selected != _prev_emotion:
            for k in ("ser_zone", "ser_probs"):
                st.session_state.pop(k, None)
        st.session_state["detected_emotion"] = newly_selected

    current_emotion = st.session_state.get("detected_emotion")

    # ── Circumplex + Zone info ─────────────────────────────────────────────
    col_plot, col_info = st.columns([3, 2])
    with col_plot:
        fig = render_circumplex(selected_emotion=current_emotion)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with col_info:
        if current_emotion:
            ser_zone = st.session_state.get("ser_zone")

            if ser_zone:
                # SER path: show voice-detected zone
                zone = ser_zone
                meta = EMOTION_COORDS.get(current_emotion, {"color": "var(--muted)"})
                badge_html = _render_zone_badge(zone)
                face = emotion_icon(current_emotion, size=36, color=meta["color"])
                st.markdown(
                    f'<div style="background:var(--surface); border:1px solid var(--border); '
                    f'border-radius:var(--radius-md); padding:16px; margin-top:20px;">'
                    f'<div style="margin-bottom:8px;">{face}</div>'
                    f'<div style="font-family:var(--font-display); font-size:1.2rem; font-weight:700; color:var(--ink);">'
                    f'{current_emotion.capitalize()}</div>'
                    f'<div style="font-size:0.8rem; color:var(--brand); margin-top:4px;">{icon("mic", 13)} Voice-detected zone</div>'
                    f'{badge_html}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                # Manual path: VA coordinates → zone
                try:
                    V, A = emotion_to_va(current_emotion)
                    zone = classify_zone(V, A)
                    meta = EMOTION_COORDS[current_emotion]
                    badge_html = _render_zone_badge(zone, V, A)
                except (ValueError, KeyError):
                    zone = "NEUTRAL_BASELINE"
                    meta = {"color": "var(--muted)"}
                    badge_html = _render_zone_badge(zone)

                face = emotion_icon(current_emotion, size=36, color=meta["color"])
                st.markdown(
                    f'<div style="background:var(--surface); border:1px solid var(--border); '
                    f'border-radius:var(--radius-md); padding:16px; margin-top:20px;">'
                    f'<div style="margin-bottom:8px;">{face}</div>'
                    f'<div style="font-family:var(--font-display); font-size:1.2rem; font-weight:700; color:var(--ink);">'
                    f'{current_emotion.capitalize()}</div>'
                    f'{badge_html}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            confidence = st.slider(
                "How confident are you in this emotion? (for research data)",
                min_value=1, max_value=5, value=3, step=1,
                format="%d/5",
            )
            st.session_state["emotion_confidence"] = confidence / 5.0
        else:
            st.info("Select an emotion above to see its affective zone.")

    st.divider()

    if current_emotion:
        if st.button("Get Recommendations →", type="primary"):
            _clear_reco_cache()
            st.switch_page("pages/04_recommendations.py")
    else:
        st.button("Get Recommendations →", disabled=True)
        st.caption("Please select an emotion first.")


show()
