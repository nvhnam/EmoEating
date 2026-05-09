from __future__ import annotations

import streamlit as st

SHIMMER_CSS = """
<style>
@keyframes shimmer {
    0%   { background-position: -400px 0; }
    100% { background-position:  400px 0; }
}
.skeleton-shimmer {
    background: linear-gradient(90deg, #f0f0f0 25%, #e0e8f0 50%, #f0f0f0 75%);
    background-size: 800px 100%;
    animation: shimmer 1.4s ease-in-out infinite;
    border-radius: 4px;
}
.skeleton-panel {
    background: #ffffff; border: 1px solid #e2e8f0;
    border-radius: 8px; padding: 12px 16px; margin-top: 6px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
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
        "<span style=\"font-size:11px; color:#9ca3af;\">📍 Finding nearby restaurants...</span>"
        f"{bars}"
        "</div>"
    )
