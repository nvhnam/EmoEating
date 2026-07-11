"""
Page 3 — Emotion Detection.

Single-path flow: a short voice check-in with a Gemini agent is the only
entry point users see by default — the live conversational elicitation is
one of this paper's core contributions, not just a capture mechanism.
Speech Emotion Recognition (SER) classifies the collected audio into one of
four affective zones (guide.md Phase 1 & 6); the result is shown in plain
language plus its per-class probability breakdown, with an explicit
confirm-or-adjust step, so users stay in control when inference errors
occur (per the paper's "user can correct the detected zone" contribution).
Zone codes, valence/arousal, and the SER backend name stay hidden from
participants; a researcher can reach the backend switcher by appending
`?debug=1` to the URL.

The Gemini Live conversation itself (mic capture, WebSocket, agent-voice
gate) runs almost entirely client-side in the browser plus one lightweight
server-side ephemeral-token mint (services/gemini_voice.py) — it was never
the source of the Streamlit Community Cloud SER outage. That was entirely
the classification step (funasr/emotion2vec loading a multi-GB model), now
fixed independently by sizing SER_MODEL_ID down to a smaller backbone (see
config.py) so the whole app — Gemini conversation AND classification —
runs in-process on the free tier without giving up this contribution.

If SER isn't installed/configured, the manual 11-emotion picker becomes the
primary (degraded) entry path — see _render_voice_panel()'s fallback branch.
"""

from __future__ import annotations

import base64
import streamlit as st
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from components.emotion_selector import render_emotion_selector
from components.voice_conversation import render_voice_conversation
from config import ZONE_LABELS, ZONE_PALETTE, EMOTION_COORDS, VOICE_TARGET_SPEECH_S, VOICE_TIMEOUT_S
from utils.icons import icon, emotion_icon
from theme import inject_global_theme


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clear_reco_cache() -> None:
    """Evict all recommendation caches when emotion / zone changes."""
    st.session_state.pop("recommendations", None)
    st.session_state.pop("_reco_emotion", None)
    st.session_state.pop("session_id", None)
    for _k in [k for k in st.session_state
               if k.startswith(("food_images_", "restaurants_"))]:
        del st.session_state[_k]


# Plain-language framing per affective zone — replaces raw probabilities/
# zone codes/valence-arousal in the default (non-debug) result view.
# Keyed by the same zone codes classify_zone()/predict_zone_from_audio()
# already return.
_ZONE_FRIENDLY = {
    "Q1_POS_ACT":       ("You sound upbeat and energized.", "Bright, active mood."),
    "Q2_NEG_ACT":       ("You sound tense or on edge.", "Keyed-up, stressed energy."),
    "Q3_NEG_DEACT":     ("You sound low-energy and a bit down.", "Flat, tired, subdued."),
    "NEUTRAL_BASELINE": ("You sound calm and steady.", "Even, baseline mood."),
}

# Maps a zone to a representative EMOTION_COORDS key when the raw top SER
# class isn't itself one of the 11 selectable emotions (e.g. CREMA-D's
# "fearful"/"disgusted" or emotion2vec's "other"/"unknown") — same fallback
# the confirm handler has always used, shared here so the preview icon and
# the eventually-committed `detected_emotion` never disagree.
_ZONE_EMOTION_FALLBACK = {
    "Q1_POS_ACT": "happy",
    "Q2_NEG_ACT": "stressed",
    "Q3_NEG_DEACT": "tired",
    "NEUTRAL_BASELINE": "neutral",
}


def _display_emotion_for(top_emotion: str, zone: str) -> str:
    return top_emotion if top_emotion in EMOTION_COORDS else _ZONE_EMOTION_FALLBACK.get(zone, "neutral")


def _render_debug_backend_selector() -> None:
    """Researcher/debug-only SER backend switcher — a researcher/debug
    control, not part of the "have a conversation" moment. Hidden from
    participants behind `?debug=1` so it never competes with the check-in
    flow (previously a small popover on every visit)."""
    from engine.ser_engine import current_backend, set_backend

    # crema4class deliberately excluded: its linear probe was trained on
    # emotion2vec_plus_large's 1024-d embeddings and is incompatible with the
    # smaller default backbone (config.SER_MODEL_ID) — selecting it would
    # raise at inference time (see _ser_crema.py's dimension check). Restore
    # it here once a probe is retrained for the active backbone.
    _BACKEND_OPTIONS = {
        "original": "Original 9-class (built-in classification head — works with any backbone size)",
    }
    _cur_id = current_backend()["id"]
    with st.popover("Backend", icon=":material/tune:"):
        selected_id = st.selectbox(
            "SER Backend",
            options=list(_BACKEND_OPTIONS.keys()),
            index=list(_BACKEND_OPTIONS.keys()).index(_cur_id) if _cur_id in _BACKEND_OPTIONS else 0,
            format_func=lambda k: _BACKEND_OPTIONS[k],
            key="ser_backend_selector",
            help="CREMA-D probe (crema4class) is hidden here until it's "
                 "retrained for the current backbone — see config.py.",
        )
    if selected_id != _cur_id:
        set_backend(selected_id)
        # Clear any pending SER result from the previous backend
        for k in ("_ser_zone_pending", "_ser_probs_pending", "_ser_top_emotion"):
            st.session_state.pop(k, None)


def _render_result_card(zone: str, top_emotion: str) -> None:
    """Friendly, non-technical framing of the detected affective zone."""
    ramp = ZONE_PALETTE.get(zone, ZONE_PALETTE["NEUTRAL_BASELINE"])
    headline, sub = _ZONE_FRIENDLY.get(zone, ("Here's what we picked up.", ""))
    face = emotion_icon(_display_emotion_for(top_emotion, zone), size=40, color=ramp["accent"], label="")
    st.markdown(
        f'<div class="card--hero" style="text-align:left; '
        f'background:{ramp["tint"]}; border:1px solid {ramp["core"]}44;">'
        f'<div style="margin-bottom:10px;">{face}</div>'
        f'<div style="font-family:var(--font-display); font-size:1.35rem; font-weight:700; color:var(--ink);">'
        f'{headline}</div>'
        f'<div style="font-size:0.9rem; color:var(--muted); margin-top:4px;">{sub}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_manual_path() -> None:
    """Manual 11-emotion picker — a correction affordance shown only after
    a voice result (state E), or the primary path when SER is unavailable/
    unconfigured (degraded entry). Never an upfront, equal-weight tab."""
    _prev_emotion = st.session_state.get("detected_emotion")
    newly_selected = render_emotion_selector(selected=_prev_emotion)
    if newly_selected:
        # Manual selection clears any prior SER zone; compare against pre-component snapshot
        if newly_selected != _prev_emotion:
            for k in ("ser_zone", "ser_probs"):
                st.session_state.pop(k, None)
        st.session_state["detected_emotion"] = newly_selected
        # A manual pick resolves any in-flight "adjust" review — the same
        # pending-state cleanup "Redo conversation" already performs when a
        # voice result is fully discarded.
        if st.session_state.get("_show_manual_correct"):
            for k in ("_ser_zone_pending", "_ser_probs_pending", "_ser_top_emotion", "_show_manual_correct"):
                st.session_state.pop(k, None)
            # Clearing both ser_zone/probs (above) and _ser_zone_pending here
            # can make the very next render of _render_voice_panel() fall
            # through to State A — bump seq so that remounts a fresh
            # voice_conversation component rather than a stale instance.
            st.session_state["_voice_component_seq"] = st.session_state.get("_voice_component_seq", 0) + 1
            st.rerun()


# ── SER voice panel ───────────────────────────────────────────────────────────

def _render_voice_panel() -> None:
    """
    Voice emotion detection — live conversation with a Gemini agent, the
    page's sole default entry point. Uses the "original" 9-class
    classification backend (crema4class hidden — see
    _render_debug_backend_selector()). The conversation only collects
    user-only audio; classification is a single batch call to the existing
    predict_zone_from_audio(), unchanged from the previous RAVDESS-read flow.
    """
    from engine.ser_engine import is_available as ser_available, is_remote_configured
    from services.gemini_voice import GeminiVoiceError, is_configured, mint_ephemeral_token

    if st.query_params.get("debug") == "1":
        _render_debug_backend_selector()

    if not ser_available():
        if is_remote_configured():
            # This deployment routes SER to a remote server (config.SER_REMOTE_URL) —
            # a "pip install" instruction would be a dead end here since there's no
            # local funasr to install. The server is just unreachable/misconfigured.
            st.warning(
                "Voice mood detection isn't available right now — please select "
                "your mood below.",
                icon=":material/warning:",
            )
        else:
            st.warning(
                "SER module not installed. "
                "Run `pip install funasr modelscope` and restart to enable voice detection.",
                icon=":material/warning:",
            )
        st.markdown("**Select how you're feeling:**")
        _render_manual_path()
        return

    if not is_configured():
        st.warning(
            "Voice check-in is not configured. Add `GEMINI_API_KEY` to your `.env` "
            "file to enable the live conversation.",
            icon=":material/warning:",
        )
        st.markdown("**Select how you're feeling:**")
        _render_manual_path()
        return

    show_manual_correct = st.session_state.get("_show_manual_correct", False)

    # ── State C/D — a voice result is awaiting the user's decision ─────────
    if "_ser_zone_pending" in st.session_state:
        zone = st.session_state["_ser_zone_pending"]
        probs = st.session_state["_ser_probs_pending"]
        sorted_probs = sorted(probs.items(), key=lambda x: x[1], reverse=True)
        top_emotion = sorted_probs[0][0]

        _render_result_card(zone, top_emotion)

        st.markdown("**Emotion probabilities**")
        for emo, prob in sorted_probs:
            st.progress(min(prob, 1.0), text=f"{emo.capitalize()}: {prob:.1%}")

        if show_manual_correct:
            st.markdown("**Pick the mood that fits better:**")
            _render_manual_path()
            if st.button("← Back to voice result", key="cancel_adjust_pending"):
                st.session_state["_show_manual_correct"] = False
                st.rerun()
        else:
            col_yes, col_adjust, col_redo = st.columns(3)
            with col_yes:
                if st.button("Yes, that's right →", type="primary", key="confirm_ser", use_container_width=True):
                    _clear_reco_cache()
                    top_emo = st.session_state.pop("_ser_top_emotion", "neutral")
                    display_emotion = _display_emotion_for(top_emo, zone)
                    st.session_state["detected_emotion"] = display_emotion
                    st.session_state["ser_zone"]  = st.session_state.pop("_ser_zone_pending", zone)
                    st.session_state["ser_probs"] = st.session_state.pop("_ser_probs_pending", probs)
                    st.session_state["_voice_component_seq"] += 1
                    st.rerun()
            with col_adjust:
                if st.button("Not quite — adjust", key="adjust_ser", use_container_width=True):
                    st.session_state["_show_manual_correct"] = True
                    st.rerun()
            with col_redo:
                if st.button("Redo conversation", key="discard_ser", use_container_width=True):
                    for k in ("_ser_zone_pending", "_ser_probs_pending", "_ser_top_emotion", "_voice_token"):
                        st.session_state.pop(k, None)
                    st.session_state["_show_manual_correct"] = False
                    st.session_state["_voice_component_seq"] += 1
                    st.rerun()
        return

    # ── Already confirmed — a voice-assigned zone is active ─────────────────
    if st.session_state.get("ser_zone"):
        sz = st.session_state["ser_zone"]
        st.success(
            f"Voice zone active: **{ZONE_LABELS.get(sz, sz)}** — "
            "this overrides zone classification for recommendations.",
            icon=":material/check_circle:",
        )
        if show_manual_correct:
            st.markdown("**Pick the mood that fits better:**")
            _render_manual_path()
            if st.button("← Keep voice result", key="cancel_adjust_confirmed"):
                st.session_state["_show_manual_correct"] = False
                st.rerun()
        else:
            col_adjust, col_clear = st.columns(2)
            with col_adjust:
                if st.button("Adjust mood", icon=":material/edit:", key="adjust_confirmed_ser", use_container_width=True):
                    st.session_state["_show_manual_correct"] = True
                    st.rerun()
            with col_clear:
                if st.button("Clear voice result", key="clear_ser", use_container_width=True):
                    for k in ("ser_zone", "ser_probs"):
                        st.session_state.pop(k, None)
                    _clear_reco_cache()
                    st.session_state["_show_manual_correct"] = False
                    # Bump seq so falling back to State A remounts a fresh
                    # voice_conversation component instance rather than one
                    # that might still hold an in-flight/stale session.
                    st.session_state["_voice_component_seq"] += 1
                    st.rerun()
        return

    # ── State A — idle, the voice hero is the only entry point ─────────────
    st.markdown(
        '<p style="color:var(--muted); font-size:0.95rem; max-width:520px;">'
        "Have a short, natural voice check-in — about a minute of easy "
        "conversation. We listen only to <i>how</i> you sound, never the "
        "words, to match meals to your mood. Nothing to read or rehearse.</p>",
        unsafe_allow_html=True,
    )

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

        st.markdown(
            '<div style="display:flex; justify-content:center; gap:12px; flex-wrap:wrap; margin-top:8px;">'
            f'<span class="chip">{icon("mic", 13, label="")} Only your voice is analyzed</span>'
            f'<span class="chip">{icon("clock", 13, label="")} ~1 minute</span>'
            f'<span class="chip">{icon("redo", 13, label="")} You can redo it</span>'
            '</div>',
            unsafe_allow_html=True,
        )

        if result is not None:
            # ── Analysis phase ───────────────────────────────────────
            # The conversation collected user-only audio; classification
            # is the SAME single batch call the RAVDESS flow used. No backend/
            # model identifiers are surfaced here — participants only see that
            # the system is working and that there's nothing for them to do.
            loading = st.empty()
            loading.markdown(
                '<div class="ser-loading card" role="status" aria-busy="true">'
                '<span class="ser-pulse" aria-hidden="true"></span>'
                '<span>'
                '<span style="font-weight:600; color:var(--ink);">'
                'Reading your mood from your voice</span><br>'
                '<span style="font-size:12.5px; color:var(--muted);">'
                'This only takes a moment — nothing to do but wait.</span>'
                '</span>'
                '</div>',
                unsafe_allow_html=True,
            )
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
                loading.empty()
                st.warning(f"SER not available: {str(exc)[:120]}")
            except RuntimeError as exc:
                loading.empty()
                st.error(
                    f"Voice analysis failed — try redoing the conversation. "
                    f"Details: {str(exc)[:200]}"
                )


# ── Main page ─────────────────────────────────────────────────────────────────

def show():
    inject_global_theme()
    st.title("How are you feeling right now?")
    st.markdown(
        "Your emotional state guides which nutrients your body may benefit from."
    )

    _render_voice_panel()

    current_emotion = st.session_state.get("detected_emotion")

    st.divider()

    if current_emotion:
        # Voice-confirmed already announces the zone via its own success
        # banner above; only add this line for the manual/degraded/adjusted
        # paths, where nothing else names what's about to be used.
        if not st.session_state.get("ser_zone"):
            st.markdown(
                '<div style="display:flex; align-items:center; gap:8px; margin-bottom:12px;">'
                f'{emotion_icon(current_emotion, size=28, color="var(--brand)", label="")}'
                f'<span style="font-weight:600; color:var(--ink);">Proceeding as: {current_emotion.capitalize()}</span>'
                '</div>',
                unsafe_allow_html=True,
            )

        if st.button("Get Recommendations →", type="primary", use_container_width=True):
            _clear_reco_cache()
            st.switch_page("pages/04_recommendations.py")
    else:
        st.button("Get Recommendations →", disabled=True, use_container_width=True)
        st.caption("Please complete the check-in above first.")


show()
