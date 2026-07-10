"""
Pipeline stepper — mirrors the paper's Figure 1 overview diagram, giving
readers of the Methodology page an instant UI-to-paper mapping before they
descend into per-stage detail (formulas/tables/live demos).
"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from utils.icons import icon

# (icon name, label, accent CSS var) — accent walks brand -> zone hues -> brand,
# echoing the pipeline's SER -> zone -> scoring -> output shape without
# claiming a specific zone for stages that aren't zone-specific.
_STAGES = [
    ("chat",   "Conversation"),
    ("mic",    "Speech Emotion Recognition"),
    ("target", "Affective Zone"),
    ("vector", "Nutritional Need Vector"),
    ("star",   "Score meals (ENMS)"),
    ("list",   "Rank & display"),
    ("map",    "Map dining options"),
]


def render_pipeline_stepper() -> None:
    """Render the 7-stage EmoEating pipeline as connected, wrapping chips."""
    chips = []
    for i, (icon_name, label) in enumerate(_STAGES):
        chips.append(
            f'<div style="display:flex; align-items:center; gap:6px; '
            f'background:var(--card); border:1px solid var(--border); '
            f'border-radius:var(--radius-pill); padding:6px 12px 6px 10px; '
            f'white-space:nowrap; box-shadow:var(--shadow-sm);">'
            f'<span style="color:var(--brand);">{icon(icon_name, 16)}</span>'
            f'<span style="font-size:12px; font-weight:600; color:var(--ink);">'
            f'<span style="color:var(--muted); font-weight:500;">{i + 1}.</span> {label}</span>'
            f'</div>'
        )
        if i < len(_STAGES) - 1:
            chips.append(
                f'<span style="color:var(--border); font-size:16px; flex:0 0 auto;">&#8594;</span>'
            )

    st.markdown(
        f'<div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap; '
        f'margin:8px 0 20px 0;">{"".join(chips)}</div>',
        unsafe_allow_html=True,
    )
