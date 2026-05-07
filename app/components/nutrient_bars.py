"""
Renders N(V,A) nutritional weight vector as horizontal bars.
"""

from __future__ import annotations

import streamlit as st
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import NUTRIENT_DISPLAY
from engine.need_vector import NeedVector, need_vector_to_dict


def render_nutrient_bars(need: NeedVector) -> None:
    """Render horizontal bars for each nutritional weight."""
    weights = need_vector_to_dict(need)

    st.markdown("**Nutritional Need Weights**")
    for key, label in NUTRIENT_DISPLAY:
        val = weights.get(key, 0.0)
        is_penalty = key == "sugar_penalty"
        color = "#E24B4A" if is_penalty else "#4a90d9"
        bar_label = f"↓ {label}" if is_penalty else label

        col1, col2 = st.columns([3, 1])
        with col1:
            pct = int(val * 100)
            bar_html = f"""
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
                <span style="font-size:12px; color:#6b7280; width:160px; flex-shrink:0;">{bar_label}</span>
                <div style="flex:1; background:#e2e8f0; border-radius:3px; height:6px; overflow:hidden;">
                    <div style="width:{pct}%; background:{color}; height:100%; border-radius:3px;"></div>
                </div>
                <span style="font-size:11px; color:#1a1a2e; width:32px; text-align:right;">{val:.2f}</span>
            </div>
            """
            st.markdown(bar_html, unsafe_allow_html=True)
