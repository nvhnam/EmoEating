from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from utils.icons import icon

SHIMMER_CSS = """
<style>
@keyframes shimmer {
    0%   { background-position: -400px 0; }
    100% { background-position:  400px 0; }
}
.skeleton-shimmer {
    background: linear-gradient(90deg, var(--border) 25%, var(--brand-tint) 50%, var(--border) 75%);
    background-size: 800px 100%;
    animation: shimmer 1.4s ease-in-out infinite;
    border-radius: 4px;
}
.skeleton-panel {
    background: var(--card); border: 1px solid var(--border);
    border-radius: var(--radius-md); padding: 12px 16px; margin-top: 6px;
    box-shadow: var(--shadow-sm);
}
</style>
"""


def inject_shimmer_css() -> None:
    if not st.session_state.get("_shimmer_css_injected"):
        st.markdown(SHIMMER_CSS, unsafe_allow_html=True)
        st.session_state["_shimmer_css_injected"] = True


def render_restaurant_skeleton(n_rows: int = 3) -> str:
    widths = ["75%", "50%", "35%"]
    bars = "".join(
        f'<div class="skeleton-shimmer" style="height:12px; width:{widths[i % 3]}; margin:6px 0;"></div>'
        for i in range(n_rows)
    )
    return (
        '<div class="skeleton-panel">'
        f'<span style="font-size:11px; color:var(--muted);">{icon("location", 11)} Finding nearby restaurants...</span>'
        f"{bars}"
        "</div>"
    )
