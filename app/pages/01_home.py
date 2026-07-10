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


def show():
    st.markdown(
        """
        <div style="text-align:center; padding:40px 20px 20px 20px;">
            <h1 style="font-size:clamp(2.2rem, 1.8rem + 2vw, 3rem); color:var(--ink); font-weight:700; margin-bottom:8px; letter-spacing:-0.02em;">
                EmoEating
            </h1>
            <p style="font-size:1.1rem; color:var(--muted); max-width:600px; margin:0 auto 24px auto;">
                Emotion-aware meal recommendations grounded in affective neuroscience
                and physiological personalisation.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            """
            <div style="
                background:var(--card); border:1px solid var(--border);
                border-radius:var(--radius-md); padding:24px; margin-bottom:20px;
                box-shadow:var(--shadow-sm);
            ">
                <h3 style="color:var(--ink); font-size:1rem; margin-bottom:8px;">
                    How it works
                </h3>
                <ol style="color:var(--muted); font-size:0.9rem; padding-left:18px;">
                    <li>Tell us how you are feeling right now</li>
                    <li>Optionally share your physiological profile</li>
                    <li>Receive research-backed meal recommendations</li>
                </ol>
            </div>
            """,
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

        if st.button("Start →", type="primary", use_container_width=True, disabled=not consent):
            if "session_token" not in st.session_state:
                st.session_state["session_token"] = str(uuid.uuid4())
            st.session_state["consented"] = True
            st.switch_page("pages/02_profile.py")
        if not consent:
            st.caption("Please consent to proceed.")

show()
