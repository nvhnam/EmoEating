"""
Individual meal recommendation card component.
"""

from __future__ import annotations

import streamlit as st
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import html as _html

from utils.formatting import fmt_kcal, fmt_time, fmt_score, kcal_match_pct
from utils.icons import icon
from components.food_image_gallery import render_food_image_gallery
from config import USE_VN_DATA, NUTRIENT_DISPLAY_LABELS, MACRO_COLORS

_MACRO_LABELS = {"carb": "Carbs", "prot": "Protein", "fat": "Fat"}


def render_meal_card(
    food: dict,
    rank: int,
    meal_kcal_target: float | None = None,
    session_id: int | None = None,
) -> bool:
    """
    Render a single meal recommendation card.
    Returns True if the user clicked "I'll eat this".
    """
    name = food.get("name", "Unknown")
    cuisine = food.get("cuisine") or ""
    kcal = food.get("calories_kcal")
    score = food.get("enms", food.get("final_score", 0.0))
    score_macro = food.get("macro_score")
    score_micro = food.get("micro_score")
    score_pref = food.get("pref_score")
    macro_breakdown = food.get("macro_breakdown", {})
    prep = food.get("prep_time_min")
    cook = food.get("cook_time_min")
    is_veg = food.get("is_vegetarian", False)
    is_vegan = food.get("is_vegan", False)
    is_gf = food.get("is_gluten_free", False)
    food_id = food.get("id")

    safe_name = _html.escape(name)
    safe_cuisine = _html.escape(cuisine) if cuisine else ""
    cuisine_span = (
        f'<span style="font-size:11px; color:var(--muted); margin-left:8px;">{safe_cuisine}</span>'
        if safe_cuisine else ""
    )

    # Vietnamese name shown beneath English name when VN dataset is active
    vn_name_raw = food.get("description") or ""
    vn_name_html = ""
    if USE_VN_DATA and vn_name_raw and vn_name_raw.strip().lower() not in ("none", "nan", ""):
        safe_vn = _html.escape(vn_name_raw.strip()[:120])
        vn_name_html = (
            f'<div style="font-size:13px; color:var(--muted); margin-top:2px; margin-left:6px;">'
            f'({safe_vn})</div>'
        )

    # Caloric info — skip entirely when kcal is unavailable (no dash rendered)
    kcal_html = ""
    if kcal:
        kcal_str = fmt_kcal(kcal)
        if meal_kcal_target:
            pct = kcal_match_pct(kcal, meal_kcal_target)
            bar_w = int(pct * 100)
            kcal_html = (
                f'<div style="margin:8px 0 8px 0;">'
                f'<span class="num" style="font-size:13px; color:var(--ink);">{kcal_str}</span>'
                f'<span class="num" style="font-size:11px; color:var(--muted);"> / target {fmt_kcal(meal_kcal_target)}</span>'
                f'<div role="progressbar" aria-label="Calorie match to target" '
                f'aria-valuenow="{bar_w}" aria-valuemin="0" aria-valuemax="100" '
                f'style="background:var(--border); border-radius:3px; height:4px; margin-top:4px;">'
                f'<div style="width:{bar_w}%; background:var(--brand); height:100%; border-radius:3px;"></div>'
                f'</div></div>'
            )
        else:
            kcal_html = f'<div class="num" style="font-size:13px; color:var(--ink); margin:8px 0 6px 0;">{kcal_str}</div>'

    # Macro fulfillment chips (actual / target per macro)
    chips_html = ""
    if macro_breakdown:
        for macro, details in macro_breakdown.items():
            color_var = f"var(--macro-{macro})" if macro in MACRO_COLORS else "var(--muted)"
            label = _MACRO_LABELS.get(macro, macro.capitalize())
            actual = details.get("actual_g", 0)
            target = details.get("target_g", 0)
            pct = int(min(details.get("ratio", 0), 1.0) * 100)
            chips_html += (
                f'<span style="background:color-mix(in srgb, {color_var} 15%, white); color:{color_var}; '
                f'border:1px solid {color_var}; font-size:10px; font-weight:600; '
                f'padding:3px 8px; border-radius:var(--radius-pill); margin-right:4px; '
                f'display:inline-block; margin-bottom:4px;">'
                f'{label}: <span class="num">{actual}g / {target}g ({pct}%)</span></span>'
            )

    # Time + dietary flags
    time_str = ""
    if prep or cook:
        total = (prep or 0) + (cook or 0)
        time_str = f'{icon("clock", 13)} {fmt_time(total)}'
    flags = []
    if is_vegan:
        flags.append(f'{icon("leaf", 13)} Vegan')
    elif is_veg:
        flags.append(f'{icon("leaf", 13)} Vegetarian')
    if is_gf:
        flags.append(f'{icon("check", 13)} Gluten-free')
    meta_line = "&nbsp;&nbsp;&nbsp;".join(filter(None, [time_str] + flags))
    meta_html = (
        f'<div style="font-size:12px; color:var(--muted); margin-top:2px;">{meta_line}</div>'
        if meta_line else ""
    )

    # ENMS component breakdown — keeps the score traceable to its 3 inputs
    # (macro/micro/preference) rather than a single opaque number, per the
    # paper's transparency claim. Purely presentational: reads existing
    # food["macro_score"|"micro_score"|"pref_score"], computes nothing.
    breakdown_html = ""
    if score_macro is not None and score_micro is not None and score_pref is not None:
        breakdown_html = (
            f'<div class="num" style="font-size:10px; color:var(--muted); margin-top:2px;">'
            f'macro {fmt_score(score_macro)} &middot; micro {fmt_score(score_micro)} '
            f'&middot; preference {fmt_score(score_pref)}</div>'
        )

    is_top = rank == 1
    card_class = "meal-card meal-card--hero" if is_top else "meal-card"
    # Rank medal chip — mono digit, distinct fill for #1 so hierarchy isn't
    # carried by the card border alone (fixes color-only + adds a legible
    # "this is the best match" signal for screen readers via the text itself).
    medal_bg = "var(--brand)" if is_top else "var(--surface)"
    medal_fg = "#ffffff" if is_top else "var(--muted)"
    rank_badge = (
        f'<span class="num" style="background:{medal_bg}; color:{medal_fg}; font-size:11px; '
        f'font-weight:700; padding:2px 8px; border-radius:var(--radius-pill); '
        f'border:1px solid {"transparent" if is_top else "var(--border)"};">#{rank}</span>'
    )
    top_badge = (
        f'<span style="background:var(--brand-tint); color:var(--brand); font-size:10px; font-weight:700; '
        f'padding:2px 8px; border-radius:var(--radius-pill); margin-left:8px; '
        f'white-space:nowrap; display:inline-block; vertical-align:middle;">Top match</span>'
        if is_top else ""
    )

    with st.container():
        st.markdown(
            f'<div class="{card_class}">'
            f'<div style="display:flex; justify-content:space-between; align-items:flex-start;">'
            f'<div>'
            f'{rank_badge}'
            f'<span style="font-family:var(--font-display); font-size:clamp(15px,4.2vw,18px); font-weight:700; color:var(--ink); margin-left:8px;">{safe_name}</span>'
            f'{cuisine_span}{top_badge}'
            f'{vn_name_html}'
            f'</div>'
            f'<div style="text-align:right;">'
            f'<span class="num" style="background:var(--brand-tint); color:var(--brand); font-size:11px; font-weight:600; padding:3px 10px; border-radius:var(--radius-pill); white-space:nowrap;">ENMS {fmt_score(score)}</span>'
            f'{breakdown_html}'
            f'</div>'
            f'</div>'
            f'{kcal_html}'
            f'{chips_html}'
            f'{meta_html}'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Expandable detail
        with st.expander("More details"):
            detail_col1, detail_col2 = st.columns(2)
            with detail_col1:
                st.markdown("**Nutrients (per 100g)**")
                nutrient_rows = [
                    ("Calories",     fmt_kcal(food.get("calories_kcal"))),
                    ("Protein",      f"{food.get('protein_g') or '—'}g"),
                    ("Carbs",        f"{food.get('carbohydrate_g') or '—'}g"),
                    ("  Complex",    f"{food.get('complex_carbs_g') or '—'}g"),
                    ("  Sugar",      f"{food.get('sugar_g') or '—'}g"),
                    ("Fiber",        f"{food.get('fiber_g') or '—'}g"),
                    ("Fat",          f"{food.get('fat_g') or '—'}g"),
                    ("Omega-3",      f"{food.get('omega3_mg') or '—'}mg"),
                    ("Magnesium",    f"{food.get('magnesium_mg') or '—'}mg"),
                    ("Iron",         f"{food.get('iron_mg') or '—'}mg"),
                    ("Vit C",        f"{food.get('vitamin_c_mg') or '—'}mg"),
                    ("Vit E",        f"{food.get('vitamin_e_mg') or '—'}mg"),
                    ("Vit B6",       f"{food.get('vitamin_b6_mg') or '—'}mg"),
                    ("Vit B12",      f"{food.get('vitamin_b12_mcg') or '—'}µg"),
                    ("Vit D",        f"{food.get('vitamin_d_mcg') or '—'}µg"),
                    ("Folate",       f"{food.get('folate_mcg') or '—'}µg"),
                ]
                for label, val in nutrient_rows:
                    st.markdown(
                        f'<div style="display:flex;justify-content:space-between;font-size:12px;">'
                        f'<span style="color:var(--muted)">{label}</span><span class="num">{val}</span></div>',
                        unsafe_allow_html=True,
                    )
            with detail_col2:
                micro_cov = food.get("micronutrient_coverage", {})
                covered = micro_cov.get("covered", [])
                if covered:
                    st.markdown("**Micronutrient Highlights** *(informational)*")
                    for item in covered[:5]:
                        n_label = NUTRIENT_DISPLAY_LABELS.get(item["nutrient"], item["nutrient"])
                        pct = item.get("pct_of_meal_target", 0)
                        st.markdown(
                            f'<div style="display:flex; justify-content:space-between; '
                            f'font-size:11px; color:var(--muted); margin-bottom:2px;">'
                            f'<span>{n_label}</span>'
                            f'<span class="num">{item["actual"]:.1f} ({pct:.0f}% RDA/meal)</span></div>',
                            unsafe_allow_html=True,
                        )

                ingr = food.get("ingredients", [])
                if ingr:
                    st.markdown("**Ingredients**")
                    st.caption(", ".join(str(i) for i in ingr[:20]))

        render_food_image_gallery(
            food_name=name,
            food_id=food_id,
            image_url=food.get("image_url"),
        )

        # return ate_it
