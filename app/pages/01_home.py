"""
Page 1 â€” Home / Landing page.
Displays research title, brief description, ethics statement, and consent flow.
"""

from __future__ import annotations

import streamlit as st
import uuid
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from theme import inject_global_theme
from utils.icons import icon

_STEPS = [
    ("chat", "Chat about your day", "A short voice check-in with an AI conversational agent — about a minute, nothing to rehearse."),
    ("target", "We sense your mood", "Speech patterns — not your words — reveal how you're feeling right now."),
    ("star", "Get matched meals", "Recommendations grounded in nutrition science, transparently scored."),
]


def show():
    inject_global_theme()

    # Hero surface — eyebrow + display heading + tagline on a raised
    # gradient panel, replacing the flat centered text block.
    st.markdown(
        """
        <div class="card--hero" style="text-align:center; padding:48px 24px 40px 24px; margin-bottom:24px;">
            <div class="eyebrow" style="display:block;">UIST 2026 &middot; Research demo</div>
            <h1 style="font-size:clamp(2.2rem, 1.8rem + 2vw, 3rem); color:var(--ink); font-weight:700; margin-bottom:10px; letter-spacing:-0.02em;">
                EmoEating
            </h1>
            <p style="font-size:1.1rem; color:var(--muted); max-width:520px; margin:0 auto;">
                Meal recommendations that meet you where your mood is —
                sensed from how you sound, not what you type.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        step_chips = "".join(
            f'<div style="flex:1 1 200px; text-align:left;">'
            f'<div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">'
            f'<span class="num" style="display:inline-flex; align-items:center; justify-content:center; '
            f'width:24px; height:24px; border-radius:50%; background:var(--gradient-brand); '
            f'color:#fff; font-size:12px; font-weight:700; flex-shrink:0;">{i}</span>'
            f'<span style="color:var(--brand);">{icon(name, 18, label="")}</span>'
            f'<span style="font-weight:600; color:var(--ink); font-size:0.95rem;">{title}</span>'
            f'</div>'
            f'<p style="color:var(--muted); font-size:0.85rem; margin:0 0 0 32px;">{body}</p>'
            f'</div>'
            for i, (name, title, body) in enumerate(_STEPS, start=1)
        )
        st.markdown(
            f'<div class="card" style="padding:24px; margin-bottom:20px;">'
            f'<div class="eyebrow">How it works</div>'
            f'<div style="display:flex; flex-wrap:wrap; gap:20px; margin-top:8px;">{step_chips}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        st.info(
            "**Research notice:** This application collects anonymous usage data "
            "for academic research purposes as part of a UIST 2026 submission. "
            "No personally identifiable information is stored.",
            icon=":material/info:",
        )

        consent = st.checkbox(
            "I understand that anonymous interaction data will be collected for research purposes "
            "and I consent to participate.",
        )

        if st.button("Begin check-in →", type="primary", use_container_width=True, disabled=not consent):
            if "session_token" not in st.session_state:
                st.session_state["session_token"] = str(uuid.uuid4())
            st.session_state["consented"] = True
            st.switch_page("pages/02_profile.py")
        if not consent:
            st.caption("Please consent to proceed.")

show()
