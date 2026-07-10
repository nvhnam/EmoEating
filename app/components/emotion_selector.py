"""
11-emotion grid selector component.
Renders buttons with a tokenized SVG face icon + label; highlights the
selected emotion.
"""

from __future__ import annotations

import streamlit as st
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import EMOTION_COORDS
from utils.icons import emotion_icon, icon


def render_emotion_selector(selected: str | None = None) -> str | None:
    """
    Render a 5-column grid of emotion buttons.
    Returns the newly selected emotion label, or None if no change.
    """
    emotions = list(EMOTION_COORDS.items())
    n_cols = 5
    rows = [emotions[i:i + n_cols] for i in range(0, len(emotions), n_cols)]

    selected_this_render = None

    # Keyed container so phase-9 responsive CSS can retarget this specific
    # 5-column grid (`.st-key-emotion-grid`) at narrower breakpoints without
    # touching other st.columns() layouts on the page.
    with st.container(key="emotion-grid"):
        for row in rows:
            cols = st.columns(len(row))
            for col, (emotion, meta) in zip(cols, row):
                is_active = emotion == selected

                with col:
                    face_color = "var(--brand)" if is_active else "var(--muted)"
                    # Selection state is never color-only: active also gets a
                    # check-circle badge and (below) a filled vs. outline
                    # button, so it reads correctly without relying on hue.
                    check_badge = (
                        f'<span style="position:absolute; top:-4px; right:calc(50% - 22px); '
                        f'color:var(--brand); background:var(--card); border-radius:50%; '
                        f'display:inline-flex;">{icon("check_circle", 14, label="Selected")}</span>'
                        if is_active else ""
                    )
                    st.markdown(
                        f'<div style="position:relative; text-align:center; margin-bottom:2px;">'
                        f'{emotion_icon(emotion, size=28, color=face_color, label="")}{check_badge}</div>',
                        unsafe_allow_html=True,
                    )
                    clicked = st.button(
                        emotion.capitalize(),
                        key=f"emo_btn_{emotion}",
                        use_container_width=True,
                        type="primary" if is_active else "secondary",
                    )
                    if clicked:
                        selected_this_render = emotion
                        # Commit the new selection and drop all cached recs here,
                        # in the button's own click run, so these writes are never
                        # discarded by st.switch_page() in a subsequent callback.
                        st.session_state["detected_emotion"] = emotion
                        # Manual button always means VA-based zone — clear any stale voice zone
                        st.session_state.pop("ser_zone", None)
                        st.session_state.pop("ser_probs", None)
                        st.session_state.pop("recommendations", None)
                        st.session_state.pop("_reco_emotion", None)
                        st.session_state.pop("_reco_meal_type", None)
                        st.session_state.pop("session_id", None)
                        for _k in [
                            k for k in st.session_state
                            if k.startswith(("food_images_", "restaurants_"))
                        ]:
                            del st.session_state[_k]

    return selected_this_render
