"""
EmoEating -- Streamlit entry point.
Uses st.navigation() (Streamlit >= 1.36) for multi-page routing.
"""

from __future__ import annotations

import streamlit as st
import uuid
import sys
import os

# Ensure app/ is on the path so all modules resolve correctly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="EmoEating",
    page_icon=":fork_and_knife:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Design tokens + style.css are injected from WITHIN each page's show()
# (theme.inject_global_theme()), not here — st.navigation(...).run() below
# halts further script execution in this entry file, so anything rendered
# before or after it here is silently discarded and never reaches the page
# actually shown to the user. See theme.py::inject_global_theme docstring.

# Session token assigned on first visit
if "session_token" not in st.session_state:
    st.session_state["session_token"] = str(uuid.uuid4())

# Page definitions
home_page    = st.Page("pages/01_home.py",            title="Home",            icon=":material/home:",        url_path="home")
profile_page = st.Page("pages/02_profile.py",         title="Profile",         icon=":material/person:",      url_path="profile")
emotion_page = st.Page("pages/03_emotion.py",         title="Emotion",         icon=":material/mood:",        url_path="emotion")
reco_page    = st.Page("pages/04_recommendations.py", title="Recommendations", icon=":material/restaurant:",  url_path="recommendations")
method_page  = st.Page("pages/05_methodology.py",     title="Methodology",     icon=":material/menu_book:",   url_path="methodology")

pg = st.navigation(
    [home_page, profile_page, emotion_page, reco_page, method_page],
    position="hidden",  # hide sidebar nav during user study
)
pg.run()
