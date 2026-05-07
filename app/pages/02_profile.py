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


def show():
    st.title("Your Profile")
    st.markdown(
        "Help us personalise your recommendations by sharing a few details. "
        "This is optional — you can skip and still receive emotion-based recommendations."
    )

    submitted = render_profile_form()

    if submitted:
        st.session_state["_profile_saved"] = True
        st.success("Profile saved! Proceeding to emotion selection...")

    if st.session_state.get("_profile_saved"):
        if st.button("Continue to Emotion Selection →"):
            st.switch_page("pages/03_emotion.py")
    else:
        st.divider()
        if st.button("Skip — proceed without profile", use_container_width=False):
            st.session_state["user_profile"] = None
            st.session_state.setdefault("meal_type", "dinner")
            st.session_state.setdefault("dietary_restrictions", [])
            st.switch_page("pages/03_emotion.py")

show()
