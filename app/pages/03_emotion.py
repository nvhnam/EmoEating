"""
Page 3 — Emotion Selection.
Manual 11-emotion grid + voice stub + Russell Circumplex visualisation.
"""

from __future__ import annotations

import streamlit as st
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from components.emotion_selector import render_emotion_selector
from components.circumplex_plot import render_circumplex
from engine.affect_mapper import emotion_to_va


def show():
    st.title("How are you feeling right now?")
    st.markdown(
        "Your emotional state guides which nutrients your body may benefit from. "
        "Select the emotion that best describes how you feel at this moment."
    )

    # Voice stub section
    with st.expander("🎙️ Voice analysis (coming soon)"):
        st.button(
            "🎙️ Record voice",
            disabled=True,
            help="Voice emotion detection is not yet integrated. Select your emotion below.",
        )
        st.caption(
            "When implemented, this will call `engine/affect_mapper.detect_from_audio()` "
            "to automatically detect your emotion from a short voice recording."
        )

    st.divider()
    st.markdown("**Select your emotion:**")

    # Emotion selector
    newly_selected = render_emotion_selector(
        selected=st.session_state.get("detected_emotion")
    )
    if newly_selected:
        st.session_state["detected_emotion"] = newly_selected

    current_emotion = st.session_state.get("detected_emotion")

    # Circumplex plot + VA display
    col_plot, col_info = st.columns([3, 2])
    with col_plot:
        fig = render_circumplex(selected_emotion=current_emotion)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with col_info:
        if current_emotion:
            V, A = emotion_to_va(current_emotion)
            from config import EMOTION_COORDS
            meta = EMOTION_COORDS[current_emotion]
            st.markdown(
                f"""
                <div style="
                    background:#f8f9fa; border:1px solid #e2e8f0;
                    border-radius:8px; padding:16px; margin-top:20px;
                ">
                    <div style="font-size:2rem; margin-bottom:8px;">{meta['emoji']}</div>
                    <div style="font-size:1.2rem; font-weight:700; color:#1a1a2e;">
                        {current_emotion.capitalize()}
                    </div>
                    <div style="font-size:0.85rem; color:#6b7280; margin-top:8px;">
                        Valence: <b>{V:+.2f}</b><br>
                        Arousal: <b>{A:+.2f}</b>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            confidence = st.slider(
                "How confident are you in this emotion? (for research data)",
                min_value=1, max_value=5, value=3, step=1,
                format="%d/5",
            )
            st.session_state["emotion_confidence"] = confidence / 5.0
        else:
            st.info("Select an emotion above to see its affective coordinates.")

    st.divider()

    if current_emotion:
        if st.button("Get Recommendations →", type="primary"):
            st.switch_page("pages/04_recommendations.py")
    else:
        st.button("Get Recommendations →", disabled=True)
        st.caption("Please select an emotion first.")

show()
