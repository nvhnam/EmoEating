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
from config import (
    ZONE_EXPLANATIONS, ZONE_LABELS, ZONE_COLORS, ZONE_PALETTE,
    NUTRIENT_DISPLAY_LABELS, RDA_REFERENCE,
)

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
    zone_core = ZONE_PALETTE.get(need.zone, ZONE_PALETTE["NEUTRAL_BASELINE"])["core"]
    zone_tint = ZONE_PALETTE.get(need.zone, ZONE_PALETTE["NEUTRAL_BASELINE"])["tint"]

    st.markdown(
        f'<div style="'
        f'background:{zone_tint}; border-left:3px solid {zone_core}; '
        f'border-radius:4px; padding:6px 10px; margin-bottom:10px;">'
        f'<span style="font-size:11px; font-weight:700; color:{zone_core};">'
        f'Zone: {zone_label}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div style="font-size:12px; font-weight:600; color:var(--ink); margin-bottom:6px;">'
        f'Macro Targets <span style="font-weight:400; color:var(--muted);">'
        f'({int(need.meal_kcal)} kcal meal)</span></div>',
        unsafe_allow_html=True,
    )

    macro_data = [
        ("carb", need.carb_pct, need.carb_g, "4 kcal/g"),
        ("prot", need.prot_pct, need.prot_g, "4 kcal/g"),
        ("fat",  need.fat_pct,  need.fat_g,  "9 kcal/g"),
    ]

    for macro, pct, grams, unit in macro_data:
        color = f"var(--macro-{macro})"
        label = _MACRO_FULL_LABELS[macro]
        bar_w = int(pct * 100)
        weight = need.macro_weights.get(macro, 0.0)
        st.markdown(
            f"""
            <div style="margin-bottom:8px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:2px;">
                    <span style="font-size:12px; color:var(--ink);">{label}</span>
                    <span style="font-size:12px; font-weight:600; color:{color};">
                        {grams}g &nbsp;<span style="font-weight:400; color:var(--muted);font-size:10px;">({int(pct*100)}% energy · w={weight:.2f})</span>
                    </span>
                </div>
                <div style="background:var(--border); border-radius:3px; height:6px; overflow:hidden;">
                    <div style="width:{bar_w}%; background:{color}; height:100%; border-radius:3px;"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_micronutrient_info(
    need: NeedVector,
    user_sex: str = "male",
    meal_fraction: float = 1 / 3,
) -> None:
    """
    Render zone explanation and priority micronutrient chips with per-meal RDA targets.
    Stage 5 display — NO effect on ENMS scoring. Whole-day dietary guidance.
    """
    if not need.micronutrient_priorities:
        return

    explanation = ZONE_EXPLANATIONS.get(need.zone, "")
    if explanation:
        st.caption(explanation)

    st.markdown(
        '<div style="font-size:11px; font-weight:600; color:var(--muted); margin:6px 0 2px 0;">'
        'Zone Priority Micronutrients '
        '<span style="font-weight:400;">(scored in ENMS β=0.20 component)</span></div>',
        unsafe_allow_html=True,
    )

    sex_key = "female" if user_sex == "female" else "male"
    chips = ""
    for col in need.micronutrient_priorities:
        label = NUTRIENT_DISPLAY_LABELS.get(col, col)
        rda_by_sex = RDA_REFERENCE.get(col)
        if rda_by_sex:
            rda_meal = rda_by_sex[sex_key] * meal_fraction
            unit = "µg" if col.endswith("_mcg") else ("g" if col.endswith("_g") else "mg")
            rda_str = f"{rda_meal:.1f}{unit}/meal"
        else:
            rda_str = ""
        target_html = (
            f' <span style="font-weight:400; color:var(--muted);">· {rda_str}</span>'
            if rda_str else ""
        )
        chips += (
            f'<div style="background:var(--surface); color:var(--ink); '
            f'border:1px solid var(--border); font-size:10px; padding:4px 9px; '
            f'border-radius:var(--radius-sm); margin-right:4px; margin-bottom:5px; '
            f'display:inline-block; line-height:1.4;">'
            f'<span style="font-weight:600;">{label}</span>{target_html}</div>'
        )
    st.markdown(
        f'<div style="margin-top:4px;">{chips}</div>',
        unsafe_allow_html=True,
    )
