"""
Stage 3 + 5 UI components: macro target panel and micronutrient info display.

render_macro_targets()    — shows zone macro gram targets with fulfillment bars
render_micronutrient_info() — shows zone explanation and priority micronutrient chips (informational only)
"""

from __future__ import annotations

import streamlit as st
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.need_vector import NeedVector
from config import ZONE_EXPLANATIONS, ZONE_LABELS, ZONE_COLORS, NUTRIENT_DISPLAY_LABELS

_MACRO_COLORS = {
    "carb": "#FAC775",
    "prot": "#4a90d9",
    "fat":  "#5DCAA5",
}
_MACRO_FULL_LABELS = {
    "carb": "Carbohydrates",
    "prot": "Protein",
    "fat":  "Fat",
}


def render_macro_targets(need: NeedVector) -> None:
    """
    Render per-meal macro gram targets as labeled progress bars.
    Shows zone name, each macro's target grams and % of meal energy.
    """
    zone_label = ZONE_LABELS.get(need.zone, need.zone)
    zone_color = ZONE_COLORS.get(need.zone, "#888780")

    st.markdown(
        f'<div style="'
        f'background:{zone_color}22; border-left:3px solid {zone_color}; '
        f'border-radius:4px; padding:6px 10px; margin-bottom:10px;">'
        f'<span style="font-size:11px; font-weight:700; color:{zone_color};">'
        f'Zone: {zone_label}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div style="font-size:12px; font-weight:600; color:#1a1a2e; margin-bottom:6px;">'
        f'Macro Targets <span style="font-weight:400; color:#6b7280;">'
        f'({int(need.meal_kcal)} kcal meal)</span></div>',
        unsafe_allow_html=True,
    )

    macro_data = [
        ("carb", need.carb_pct, need.carb_g, "4 kcal/g"),
        ("prot", need.prot_pct, need.prot_g, "4 kcal/g"),
        ("fat",  need.fat_pct,  need.fat_g,  "9 kcal/g"),
    ]

    for macro, pct, grams, unit in macro_data:
        color = _MACRO_COLORS[macro]
        label = _MACRO_FULL_LABELS[macro]
        bar_w = int(pct * 100)
        weight = need.macro_weights.get(macro, 0.0)
        st.markdown(
            f"""
            <div style="margin-bottom:8px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:2px;">
                    <span style="font-size:12px; color:#1a1a2e;">{label}</span>
                    <span style="font-size:12px; font-weight:600; color:{color};">
                        {grams}g &nbsp;<span style="font-weight:400; color:#6b7280;font-size:10px;">({int(pct*100)}% energy · w={weight:.2f})</span>
                    </span>
                </div>
                <div style="background:#e2e8f0; border-radius:3px; height:6px; overflow:hidden;">
                    <div style="width:{bar_w}%; background:{color}; height:100%; border-radius:3px;"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_micronutrient_info(need: NeedVector) -> None:
    """
    Render zone explanation and micronutrient priority chips (informational only).
    These are Stage 5 display items — they have NO effect on ENMS scoring.
    """
    if not need.micronutrient_priorities:
        return

    explanation = ZONE_EXPLANATIONS.get(need.zone, "")
    if explanation:
        st.caption(explanation)

    st.markdown(
        '<div style="font-size:11px; font-weight:600; color:#6b7280; '
        'margin: 6px 0 4px 0;">Micronutrient Focus <span style="font-weight:400;">'
        '(informational)</span></div>',
        unsafe_allow_html=True,
    )

    chips = ""
    for col in need.micronutrient_priorities:
        label = NUTRIENT_DISPLAY_LABELS.get(col, col)
        chips += (
            f'<span style="background:#f1f5f9; color:#4b5563; '
            f'border:1px solid #d1d5db; font-size:10px; padding:2px 7px; '
            f'border-radius:10px; margin-right:4px; margin-bottom:4px; '
            f'display:inline-block;">{label}</span>'
        )
    st.markdown(
        f'<div style="line-height:2;">{chips}</div>',
        unsafe_allow_html=True,
    )
