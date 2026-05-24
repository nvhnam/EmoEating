"""
Page 3 — Emotion Detection.

Two input paths (guide.md Phase 1 & 6):
  A. Manual: 11-emotion grid → VA coordinates → zone classification
  B. Voice:  audio recording → emotion2vec_plus_large (FunASR) → 9-class softmax
             → argmax → zone lookup (bypasses VA step)

Russell Circumplex visualisation shown for both paths.
"""

from __future__ import annotations

import streamlit as st
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from components.emotion_selector import render_emotion_selector
from components.circumplex_plot import render_circumplex
from engine.affect_mapper import emotion_to_va
from engine.zone_classifier import classify_zone
from config import ZONE_LABELS, ZONE_COLORS, EMOTION_COORDS


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
    zone_color = ZONE_COLORS.get(zone, "#888780")
    va_html = ""
    if V is not None and A is not None:
        va_html = (
            f'<div style="font-size:0.85rem; color:#6b7280; margin-top:6px;">'
            f'Valence: <b>{V:+.2f}</b> &nbsp; Arousal: <b>{A:+.2f}</b></div>'
        )
    return (
        f'<div style="margin-top:10px;">'
        f'<span style="background:{zone_color}22; color:{zone_color}; '
        f'border:1px solid {zone_color}; font-size:11px; font-weight:700; '
        f'padding:3px 10px; border-radius:12px;">Zone: {zone_label}</span>'
        f'</div>'
        f'{va_html}'
    )


# ── SER voice panel ───────────────────────────────────────────────────────────

def _render_voice_panel() -> None:
    """
    Voice emotion detection panel using emotion2vec_plus_large.
    Renders inside an expander. Updates session state on confirmed use.
    """
    with st.expander("🎙️ Voice Emotion Detection — emotion2vec_plus_large", expanded=False):
        st.markdown(
            "Record a short voice sample and the system will detect your emotional zone "
            "automatically using **emotion2vec_plus_large** "
            "(Ma et al., Findings of ACL 2024, trained on 42,526 h of speech). "
            "The detected zone feeds directly into the ENMS recommendation pipeline."
        )
        st.caption(
            "**User-study prompt (RAVDESS standardised sentences):** "
            "\"Kids are talking by the door.\" — record twice for best results. "
            "Speak naturally at a comfortable volume."
        )

        from engine.ser_engine import is_available as ser_available
        if not ser_available():
            st.warning(
                "SER module not installed. "
                "Run `pip install funasr modelscope` and restart to enable voice detection.",
                icon=":material/warning:",
            )

        # ── Affect grid (Phase 7 user-study ground truth) ─────────────────────
        # Participants self-report their V-A position BEFORE voice recording.
        # Stored as self_reported_v/a/zone in the session log for zone agreement analysis.
        st.markdown(
            '<div style="font-size:11px; font-weight:600; color:#6b7280; margin:10px 0 4px 0;">'
            'Step 1 — Self-Report Your Current Feeling '
            '<span style="font-weight:400;">(research ground truth)</span></div>',
            unsafe_allow_html=True,
        )
        sr_col_v, sr_col_a = st.columns(2)
        with sr_col_v:
            sr_v = st.slider(
                "Valence (pleasantness)",
                min_value=-1.0, max_value=1.0, value=0.0, step=0.05,
                format="%.2f",
                help="−1 = Very unpleasant · 0 = Neutral · +1 = Very pleasant",
                key="sr_valence",
            )
        with sr_col_a:
            sr_a = st.slider(
                "Arousal (energy level)",
                min_value=-1.0, max_value=1.0, value=0.0, step=0.05,
                format="%.2f",
                help="−1 = Very calm/sleepy · 0 = Neutral · +1 = Very alert/active",
                key="sr_arousal",
            )
        from engine.zone_classifier import classify_zone as _cz
        sr_zone = _cz(sr_v, sr_a)
        sr_color = ZONE_COLORS.get(sr_zone, "#888780")
        sr_label = ZONE_LABELS.get(sr_zone, sr_zone)
        st.markdown(
            f'<div style="font-size:11px; color:{sr_color}; font-weight:600; margin-bottom:8px;">'
            f'→ Self-reported zone: <span style="background:{sr_color}22; padding:2px 8px; '
            f'border-radius:8px; border:1px solid {sr_color};">{sr_label}</span></div>',
            unsafe_allow_html=True,
        )
        st.session_state["self_reported_v"] = sr_v
        st.session_state["self_reported_a"] = sr_a
        st.session_state["self_reported_zone"] = sr_zone

        st.markdown(
            '<div style="font-size:11px; font-weight:600; color:#6b7280; margin:6px 0 4px 0;">'
            'Step 2 — Record Voice Sample</div>',
            unsafe_allow_html=True,
        )

        # Audio input — Streamlit ≥1.37 provides st.audio_input()
        audio_val = None
        try:
            audio_val = st.audio_input(
                "Record your voice",
                key="voice_recorder",
            )
        except AttributeError:
            # Fallback for Streamlit <1.37
            uploaded = st.file_uploader(
                "Upload a voice recording (WAV, 16 kHz mono preferred)",
                type=["wav"],
                key="voice_upload",
            )
            if uploaded is not None:
                audio_val = uploaded

        if audio_val is not None:
            with st.spinner("Analysing emotion from voice (emotion2vec_plus_large)..."):
                try:
                    from engine.ser_engine import predict_zone_from_audio
                    audio_bytes = audio_val.read()
                    zone, probs = predict_zone_from_audio(audio_bytes)

                    st.markdown("**9-class emotion probabilities:**")
                    sorted_probs = sorted(probs.items(), key=lambda x: x[1], reverse=True)
                    for emo, prob in sorted_probs:
                        st.progress(
                            min(prob, 1.0),
                            text=f"{emo.capitalize()}: {prob:.1%}",
                        )

                    zone_color = ZONE_COLORS.get(zone, "#888780")
                    zone_label = ZONE_LABELS.get(zone, zone)
                    st.markdown(
                        f'<div style="margin-top:12px; padding:10px; '
                        f'background:{zone_color}22; border:1px solid {zone_color}; '
                        f'border-radius:8px;">'
                        f'<span style="font-size:12px; font-weight:700; color:{zone_color};">'
                        f'Detected Zone: {zone_label}</span>'
                        f'<div style="font-size:11px; color:#6b7280; margin-top:4px;">'
                        f'Top emotion: {sorted_probs[0][0].capitalize()} '
                        f'({sorted_probs[0][1]:.1%} confidence)</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                    # Store SER result; confirm button writes to main session state
                    st.session_state["_ser_zone_pending"] = zone
                    st.session_state["_ser_probs_pending"] = probs
                    st.session_state["_ser_top_emotion"] = sorted_probs[0][0]

                    col_confirm, col_discard = st.columns(2)
                    with col_confirm:
                        if st.button("✓ Use voice result", type="primary", key="confirm_ser"):
                            _clear_reco_cache()
                            top_emo = st.session_state.pop("_ser_top_emotion", "neutral")
                            # Use the top SER emotion if it exists in manual EMOTION_COORDS,
                            # otherwise fall back to the closest manual label per zone.
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
                            st.rerun()
                    with col_discard:
                        if st.button("✗ Re-record", key="discard_ser"):
                            for k in ("_ser_zone_pending", "_ser_probs_pending", "_ser_top_emotion"):
                                st.session_state.pop(k, None)
                            st.rerun()

                except ImportError as exc:
                    st.warning(f"SER not available: {str(exc)[:120]}")
                except RuntimeError as exc:
                    st.error(
                        f"Voice analysis failed — try re-recording. "
                        f"Details: {str(exc)[:200]}"
                    )

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

    newly_selected = render_emotion_selector(
        selected=st.session_state.get("detected_emotion")
    )
    if newly_selected:
        # Manual selection clears any prior SER zone
        if newly_selected != st.session_state.get("detected_emotion"):
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
                meta = EMOTION_COORDS.get(current_emotion, {"emoji": "🎙️", "color": "#888780"})
                badge_html = _render_zone_badge(zone)
                st.markdown(
                    f'<div style="background:#f8f9fa; border:1px solid #e2e8f0; '
                    f'border-radius:8px; padding:16px; margin-top:20px;">'
                    f'<div style="font-size:2rem; margin-bottom:8px;">{meta["emoji"]}</div>'
                    f'<div style="font-size:1.2rem; font-weight:700; color:#1a1a2e;">'
                    f'{current_emotion.capitalize()}</div>'
                    f'<div style="font-size:0.8rem; color:#4a90d9; margin-top:4px;">🎙️ Voice-detected zone</div>'
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
                    meta = {"emoji": "😐", "color": "#888780"}
                    badge_html = _render_zone_badge(zone)

                st.markdown(
                    f'<div style="background:#f8f9fa; border:1px solid #e2e8f0; '
                    f'border-radius:8px; padding:16px; margin-top:20px;">'
                    f'<div style="font-size:2rem; margin-bottom:8px;">{meta["emoji"]}</div>'
                    f'<div style="font-size:1.2rem; font-weight:700; color:#1a1a2e;">'
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
