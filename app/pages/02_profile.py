"""
Page 2 — User Profile.
Collects age, sex, height, weight, dietary restrictions, and meal type.
Computes BMI/BMR/TDEE via physiological engine.
Profile is optional — user can skip.
"""

from __future__ import annotations

import streamlit as st
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from components.profile_form import render_profile_form
from theme import inject_global_theme


def show():
    inject_global_theme()
    st.markdown('<div class="eyebrow">Step 1 of 2</div>', unsafe_allow_html=True)
    st.title("Your Profile")
    st.markdown(
        '<p style="color:var(--muted); font-size:0.95rem; max-width:640px;">'
        "Help us personalise your recommendations by sharing a few details. "
        "This is optional — you can skip and still receive emotion-based recommendations.</p>",
        unsafe_allow_html=True,
    )

    submitted = render_profile_form()

    if submitted:
        st.session_state["_profile_saved"] = True
        st.success("Profile saved! Proceeding to emotion selection...")

    if st.session_state.get("_profile_saved"):
        if st.button("Continue to Emotion Selection →", type="primary", use_container_width=True):
            st.switch_page("pages/03_emotion.py")
    else:
        st.divider()
        if st.button("Skip — proceed without profile", type="secondary", use_container_width=True):
            st.session_state["user_profile"] = None
            st.session_state.setdefault("meal_type", "dinner")
            st.session_state.setdefault("dietary_restrictions", [])
            st.switch_page("pages/03_emotion.py")

show()
