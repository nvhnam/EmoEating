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
    """Render the 7-stage EmoEating pipeline as a connected ribbon (desktop)
    that becomes a vertical stack on phones (<640px, see style.css
    `.pipeline-stepper`)."""
    chips = []
    for i, (icon_name, label) in enumerate(_STAGES):
        chips.append(
            f'<div role="listitem" class="pipeline-stage" style="display:flex; align-items:center; gap:8px; '
            f'background:var(--card); border:1px solid var(--border); '
            f'border-radius:var(--radius-pill); padding:6px 14px 6px 8px; '
            f'white-space:nowrap; box-shadow:var(--shadow-sm); flex:0 0 auto;">'
            f'<span class="num" style="display:flex; align-items:center; justify-content:center; '
            f'width:20px; height:20px; border-radius:50%; background:var(--brand); '
            f'color:#fff; font-size:11px; font-weight:700; flex-shrink:0;">{i + 1}</span>'
            f'<span style="color:var(--brand);">{icon(icon_name, 16, label="")}</span>'
            f'<span style="font-size:12px; font-weight:600; color:var(--ink);">{label}</span>'
            f'</div>'
        )
        if i < len(_STAGES) - 1:
            chips.append(
                f'<span class="pipeline-chevron" aria-hidden="true" style="color:var(--border); flex:0 0 auto; display:flex;">'
                f'{icon("chevron", 16)}</span>'
            )

    st.markdown(
        f'<div class="pipeline-stepper" role="list" aria-label="ENMS pipeline stages" '
        f'style="display:flex; align-items:center; gap:8px; flex-wrap:nowrap; '
        f'overflow-x:auto; padding:4px 2px 12px 2px; margin:8px 0 12px 0;">'
        f'{"".join(chips)}</div>',
        unsafe_allow_html=True,
    )
