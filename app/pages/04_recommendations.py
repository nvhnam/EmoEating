"""
Page 4 — Recommendations (main research output page).
Two-column layout: left context panel | right recommendation cards.

Supports two zone-input paths (guide.md Phase 6):
  Manual : emotion label → VA → classify_zone()
  SER    : ser_zone from session state (pre-computed by emotion2vec_plus_large)
"""

from __future__ import annotations

import html
import streamlit as st
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.affect_mapper import emotion_to_va, get_emotion_metadata
from engine.zone_classifier import classify_zone
from engine.need_vector import compute_need_vector
from engine.physiological import PhysiologicalProfile, profile_from_dict, meal_energy_target
from components.nutrient_bars import render_macro_targets, render_micronutrient_info
from components.meal_card import render_meal_card
from components.skeleton_loader import inject_shimmer_css, render_restaurant_skeleton
from components.restaurant_panel import render_restaurant_panel
from services.location import get_ip_location, get_browser_location, geocode_address
from services.restaurant_finder import fetch_restaurants_cached
from utils.formatting import fmt_kcal
from utils.icons import icon, emotion_icon
from config import (
    TOP_K_DEFAULT,
    MEAL_ENERGY_FRACTION,
    MEAL_TYPE_LABELS,
    ZONE_LABELS,
    ZONE_COLORS,
    ZONE_PALETTE,
    UI_DISCLAIMER,
    GOOGLE_PLACES_API_KEY,
    RESTAURANT_SEARCH_RADIUS_M,
    RESTAURANT_MAX_RESULTS,
    USE_VN_DATA,
)


def _render_location_ui(recs: list) -> None:
    st.markdown("---")
    st.markdown(
        f'<div style="display:flex; align-items:center; gap:6px; font-weight:600; font-size:14px; color:var(--ink); margin-bottom:2px;">'
        f'{icon("location", 15)} Your Location</div>',
        unsafe_allow_html=True,
    )
    st.caption("City-level only · session-scoped · no data stored")

    user_loc = st.session_state.get("user_location")
    if user_loc:
        st.success(user_loc["label"], icon=":material/location_on:")
        if st.button("Change location", key="clear_location"):
            del st.session_state["user_location"]
            for food in recs:
                st.session_state.pop(f"restaurants_{food.get('id')}", None)
            st.rerun()
    else:
        if st.button("Auto-detect my location", key="auto_detect_loc"):
            st.session_state["_geo_request"] = "pending"
            st.session_state["_geo_attempts"] = 0
            st.rerun()

        if st.session_state.get("_geo_request") == "pending":
            with st.spinner("Detecting your location..."):
                loc = get_browser_location()
            if loc:
                st.session_state["user_location"] = loc
                st.session_state.pop("_geo_request", None)
                st.session_state.pop("_geo_attempts", None)
                st.rerun()
            else:
                attempts = st.session_state.get("_geo_attempts", 0)
                if attempts < 2:
                    st.session_state["_geo_attempts"] = attempts + 1
                    st.info("Detecting your location...")
                    st.rerun()
                else:
                    loc = get_ip_location()
                    st.session_state.pop("_geo_request", None)
                    st.session_state.pop("_geo_attempts", None)
                    if loc:
                        st.session_state["user_location"] = loc
                        st.rerun()
                    else:
                        st.warning("Could not auto-detect. Enter your location below.")

        with st.form("location_form", clear_on_submit=False):
            addr = st.text_input(
                "Or enter city / address",
                placeholder="e.g. New York, NY · London, UK · Ho Chi Minh City",
            )
            st.caption("Works for any city worldwide.")
            if st.form_submit_button("Search") and addr.strip():
                with st.spinner("Geocoding..."):
                    loc = geocode_address(addr.strip(), GOOGLE_PLACES_API_KEY)
                if loc:
                    st.session_state["user_location"] = loc
                    st.rerun()
                else:
                    st.warning("Address not found. Try a different format.")


def _get_profile() -> PhysiologicalProfile | None:
    pd = st.session_state.get("user_profile")
    if not pd:
        return None
    return profile_from_dict(pd)


def _resolve_zone_and_va(emotion: str) -> tuple[str, float, float]:
    """
    Resolve the active zone and VA coordinates for this session.

    SER path  : use ser_zone from session state; VA is best-effort.
    Manual path: compute zone from VA coordinates.
    """
    ser_zone = st.session_state.get("ser_zone")
    try:
        V, A = emotion_to_va(emotion)
    except ValueError:
        V, A = 0.0, 0.0   # SER emotion label not in manual EMOTION_COORDS

    if ser_zone:
        return ser_zone, V, A
    return classify_zone(V, A), V, A


def show():
    if USE_VN_DATA:
        st.sidebar.info("🇻🇳 Vietnamese Food Dataset active")

    emotion = st.session_state.get("detected_emotion")
    if not emotion:
        st.warning("No emotion detected. Please go back and select an emotion.")
        if st.button("← Back to Emotion"):
            st.switch_page("pages/03_emotion.py")
        return

    # Read profile inputs before the cache guard so meal_type is available for comparison
    meal_type           = st.session_state.get("meal_type", "dinner")
    dietary_restrictions = st.session_state.get("dietary_restrictions", [])

    # ── Stale-cache eviction ─────────────────────────────────────────────────
    _cached_reco_emotion   = st.session_state.get("_reco_emotion")
    _cached_reco_meal_type = st.session_state.get("_reco_meal_type")
    if "recommendations" in st.session_state and (
        _cached_reco_emotion != emotion or _cached_reco_meal_type != meal_type
    ):
        st.session_state.pop("recommendations", None)
        st.session_state.pop("_reco_emotion", None)
        st.session_state.pop("_reco_meal_type", None)
        st.session_state.pop("session_id", None)
        for _k in [k for k in st.session_state
                   if k.startswith(("food_images_", "restaurants_"))]:
            del st.session_state[_k]

    profile             = _get_profile()
    session_token       = st.session_state.get("session_token", "anonymous")
    confidence          = st.session_state.get("emotion_confidence")
    ser_zone            = st.session_state.get("ser_zone")

    zone, V, A = _resolve_zone_and_va(emotion)
    meal_kcal  = meal_energy_target(profile.tdee_kcal, meal_type) if profile else None
    need       = compute_need_vector(zone, meal_kcal)
    user_sex   = profile.sex if profile else "male"
    meal_fraction = MEAL_ENERGY_FRACTION.get(meal_type.lower(), 1 / 3)

    # Best-effort emotion metadata (may be absent for SER-only emotion labels)
    try:
        meta = get_emotion_metadata(emotion)
    except ValueError:
        meta = {"color": ZONE_COLORS.get(zone, ZONE_PALETTE["NEUTRAL_BASELINE"]["accent"])}

    # ── Run recommendation engine ─────────────────────────────────────────────
    if "recommendations" not in st.session_state:
        with st.spinner("Computing recommendations..."):
            try:
                from db.connection import test_connection
                db_ok = test_connection()
            except Exception:
                db_ok = False

            if db_ok:
                from engine.recommender import get_recommendations
                recs = get_recommendations(
                    emotion=emotion,
                    meal_type=meal_type,
                    user_profile=profile,
                    dietary_restrictions=dietary_restrictions,
                    top_k=TOP_K_DEFAULT,
                    zone=ser_zone,   # None → VA-based; set → SER bypass
                )
                if not recs:
                    from config import NUTRIENT_NULL, ZONE_MICRONUTRIENT_PRIORITIES, NUTRIENT_DISPLAY_LABELS
                    _zone_micros = ZONE_MICRONUTRIENT_PRIORITIES.get(zone, [])
                    _micro_labels = [NUTRIENT_DISPLAY_LABELS.get(c, c) for c in _zone_micros]
                    if not NUTRIENT_NULL and _micro_labels:
                        st.info(
                            f"No complete-meal foods in the database have all zone-priority "
                            f"micronutrients populated ({', '.join(_micro_labels)}) for zone **{zone}**. "
                            f"Showing demo results. "
                            f"Set `NUTRIENT_NULL = True` in config.py to score foods with partial data, "
                            f"or run the full ETL pipeline with a dataset that includes these nutrients.",
                            icon=":material/info:",
                        )
                    else:
                        st.info(
                            "No meal data loaded yet — showing demo results. "
                            "Run the ETL pipeline to populate real recommendations.",
                            icon=":material/info:",
                        )
                    recs = _demo_recommendations(emotion, zone, need, profile, meal_fraction)
                else:
                    try:
                        from db.session_logger import log_recommendation_session
                        sid = log_recommendation_session(
                            session_token=session_token,
                            emotion=emotion,
                            meal_type=meal_type,
                            recommendations=recs,
                            V=V, A=A,
                            zone=zone,
                            confidence=confidence,
                            self_reported_v    = st.session_state.get("self_reported_v"),
                            self_reported_a    = st.session_state.get("self_reported_a"),
                            self_reported_zone = st.session_state.get("self_reported_zone"),
                        )
                        st.session_state["session_id"] = sid
                    except Exception:
                        pass
            else:
                st.warning(
                    "Database not connected — showing demo results. "
                    "Run ETL and connect MySQL to see real recommendations.",
                    icon=":material/info:",
                )
                recs = _demo_recommendations(emotion, zone, need, profile, meal_fraction)

        st.session_state["recommendations"]  = recs
        st.session_state["_reco_emotion"]    = emotion
        st.session_state["_reco_meal_type"]  = meal_type

    recs = st.session_state.get("recommendations", [])

    # ── Layout ───────────────────────────────────────────────────────────────
    # Wrapped in a keyed container so phase-9 responsive CSS can target this
    # specific horizontal split (`.st-key-reco-split`) without affecting the
    # other st.columns() layouts elsewhere on the page.
    reco_split = st.container(key="reco-split")
    with reco_split:
        left, right = st.columns([3, 7])

    with left:
        ramp = ZONE_PALETTE.get(zone, ZONE_PALETTE["NEUTRAL_BASELINE"])
        face = emotion_icon(emotion, size=32, color=meta.get("color", ramp["accent"]))
        source_badge = (
            f'<span style="font-size:10px; color:var(--brand); margin-top:2px;">{icon("mic", 11)} Voice-detected</span>'
            if ser_zone else ""
        )
        st.markdown(
            f'<div style="background:var(--card); border:1px solid var(--border); '
            f'border-radius:var(--radius-md); padding:16px; margin-bottom:12px; box-shadow:var(--shadow-sm);">'
            f'<div>{face}</div>'
            f'<div style="font-family:var(--font-display); font-size:1.1rem; font-weight:700; color:var(--ink); margin-top:4px;">'
            f'{emotion.capitalize()}</div>'
            f'<div style="font-size:0.8rem; color:var(--muted); margin-top:2px;">'
            f'V={V:+.2f}, A={A:+.2f}</div>'
            f'{source_badge}'
            f'</div>',
            unsafe_allow_html=True,
        )

        render_macro_targets(need)
        render_micronutrient_info(need, user_sex=user_sex, meal_fraction=meal_fraction)

        if profile:
            st.markdown("---")
            st.markdown("**Physiological Profile**")
            _target = meal_energy_target(profile.tdee_kcal, meal_type)
            st.caption(
                f"BMI: {profile.bmi:.1f} ({profile.bmi_category.capitalize()})\n\n"
                f"TDEE: {fmt_kcal(profile.tdee_kcal)}/day\n\n"
                f"{MEAL_TYPE_LABELS.get(meal_type, meal_type.capitalize())} target: ~{fmt_kcal(_target)}"
            )

        _render_location_ui(recs)

        st.markdown("---")
        st.caption(UI_DISCLAIMER)

        st.markdown("---")
        if st.button("← Adjust emotion"):
            for _k in ("recommendations", "_reco_emotion", "_reco_meal_type",
                       "session_id", "detected_emotion", "ser_zone", "ser_probs"):
                st.session_state.pop(_k, None)
            for _k in [k for k in st.session_state
                       if k.startswith(("food_images_", "restaurants_"))]:
                del st.session_state[_k]
            st.switch_page("pages/03_emotion.py")

    with right:
        meal_label = MEAL_TYPE_LABELS.get(meal_type, meal_type.capitalize())
        st.markdown(
            f"## Recommended for you "
            f'<span style="background:var(--brand-tint); color:var(--brand); '
            f'font-size:0.8rem; padding:3px 10px; border-radius:var(--radius-pill);">'
            f'{meal_label}</span>',
            unsafe_allow_html=True,
        )

        if not recs:
            st.info(
                "No meals found matching your criteria. "
                "Try adjusting your dietary restrictions or meal type."
            )
            return

        meal_kcal_target = meal_energy_target(profile.tdee_kcal, meal_type) if profile else None
        session_id = st.session_state.get("session_id")

        # Pre-fetch food images in parallel
        _to_fetch_img = [f for f in recs if f"food_images_{f.get('id')}" not in st.session_state]
        if _to_fetch_img:
            try:
                from services.food_images import fetch_food_images

                def _fetch_img(food: dict) -> tuple:
                    return food.get("id"), fetch_food_images(
                        food.get("name", ""), food.get("image_url"), 3, food.get("id")
                    )

                with ThreadPoolExecutor(max_workers=min(len(_to_fetch_img), 5)) as _img_ex:
                    for _img_fut in as_completed(
                        {_img_ex.submit(_fetch_img, f): f for f in _to_fetch_img}
                    ):
                        _fid, _urls = _img_fut.result()
                        st.session_state[f"food_images_{_fid}"] = _urls
            except Exception:
                pass

        for food in recs:
            ate_it = render_meal_card(
                food=food,
                rank=food.get("rank", 0),
                meal_kcal_target=meal_kcal_target,
                session_id=session_id,
            )
            if ate_it:
                food_id = food.get("id")
                if session_id and food_id:
                    try:
                        from db.session_logger import log_food_selection
                        log_food_selection(session_id, food_id)
                    except Exception:
                        pass
                st.session_state["selected_food"] = food
                st.success(f"Great choice! Enjoy your {food.get('name', 'meal')} 🍽️")

        # ── Nearby Restaurants ────────────────────────────────────────────────
        user_location = st.session_state.get("user_location")
        if user_location:
            inject_shimmer_css()
            st.markdown("---")
            st.markdown(
                f'<h3 style="display:flex; align-items:center; gap:8px;">{icon("map", 20)} Find these dishes near you</h3>',
                unsafe_allow_html=True,
            )
            st.caption(
                f"Showing restaurants within "
                f"**{RESTAURANT_SEARCH_RADIUS_M // 1000} km** of "
                f"**{user_location['label']}**"
            )

            lat   = user_location["lat"]
            lng   = user_location["lng"]
            lat_r = round(lat, 3)
            lng_r = round(lng, 3)

            def _restaurant_search_name(food: dict) -> str:
                if USE_VN_DATA:
                    vn = (food.get("description") or "").strip()
                    if vn and vn.lower() not in ("none", "nan"):
                        return vn
                return food.get("name", "")

            def _restaurant_label(food: dict) -> str:
                en = food.get("name", "Unknown")
                if USE_VN_DATA:
                    vn = (food.get("description") or "").strip()
                    if vn and vn.lower() not in ("none", "nan"):
                        return f"{vn} ({en})"
                return en

            _lang = "vi" if USE_VN_DATA else "en"

            placeholders: dict = {}
            for food in recs:
                fid   = food.get("id")
                label = _restaurant_label(food)[:80]
                st.markdown(
                    f'<div style="font-size:13px; font-weight:600; color:var(--ink); '
                    f'margin:10px 0 2px 0;">{html.escape(label)}</div>',
                    unsafe_allow_html=True,
                )
                placeholder = st.empty()
                placeholders[fid] = placeholder
                if f"restaurants_{fid}" not in st.session_state:
                    placeholder.markdown(
                        render_restaurant_skeleton(n_rows=3),
                        unsafe_allow_html=True,
                    )

            for food in recs:
                fid = food.get("id")
                if f"restaurants_{fid}" in st.session_state:
                    with placeholders[fid].container():
                        render_restaurant_panel(
                            fetch_result=st.session_state[f"restaurants_{fid}"],
                            food_name=food.get("name", ""),
                            rank=food.get("rank", 0),
                            session_id=st.session_state.get("session_id"),
                            food_id=fid,
                        )

            to_fetch = [f for f in recs if f"restaurants_{f.get('id')}" not in st.session_state]
            if to_fetch:
                def _fetch_one(food: dict) -> tuple:
                    fid    = food.get("id")
                    result = fetch_restaurants_cached(
                        dish_name     = _restaurant_search_name(food),
                        food_id       = fid,
                        lat_rounded   = lat_r,
                        lng_rounded   = lng_r,
                        radius_m      = RESTAURANT_SEARCH_RADIUS_M,
                        max_results   = RESTAURANT_MAX_RESULTS,
                        api_key       = GOOGLE_PLACES_API_KEY,
                        language_code = _lang,
                    )
                    return fid, result

                with ThreadPoolExecutor(max_workers=min(len(to_fetch), 5)) as executor:
                    futures = {executor.submit(_fetch_one, food): food for food in to_fetch}
                    for future in as_completed(futures):
                        fid, fetch_result = future.result()
                        st.session_state[f"restaurants_{fid}"] = fetch_result
                        food_entry = next((f for f in recs if f.get("id") == fid), {})
                        placeholders[fid].empty()
                        with placeholders[fid].container():
                            render_restaurant_panel(
                                fetch_result = fetch_result,
                                food_name    = food_entry.get("name", ""),
                                rank         = food_entry.get("rank", 0),
                                session_id   = st.session_state.get("session_id"),
                                food_id      = fid,
                            )
        else:
            st.markdown("---")
            st.info(
                "**Set your location** in the left panel to discover nearby restaurants "
                "serving these dishes.",
                icon=":material/location_on:",
            )


def _demo_recommendations(
    emotion: str,
    zone: str,
    need,
    profile,
    meal_fraction: float,
) -> list[dict]:
    """
    Fallback demo results when DB is not connected.
    Computes 3-component ENMS scores against the NeedVector so the UI renders correctly.
    """
    from config import (
        ENMS_MACRO_ALPHA, ENMS_MICRO_BETA, DEFAULT_PREF_SCORE, TOP_K_DEFAULT,
        ZONE_MICRONUTRIENT_PRIORITIES, RDA_REFERENCE, NUTRIENT_DISPLAY_LABELS,
    )

    try:
        V, A = emotion_to_va(emotion)
    except ValueError:
        V, A = 0.0, 0.0

    user_sex = profile.sex if profile else "male"
    sex_key  = "female" if user_sex == "female" else "male"
    pref_weight = 1.0 - ENMS_MACRO_ALPHA - ENMS_MICRO_BETA

    demo_foods = [
        {"id": 1, "name": "Grilled Salmon with Quinoa", "cuisine": "Mediterranean",
         "calories_kcal": 520, "protein_g": 38, "carbohydrate_g": 42, "fat_g": 18,
         "fiber_g": 5, "omega3_mg": 2000, "magnesium_mg": 60,
         "vitamin_c_mg": 15, "vitamin_b12_mcg": 4.5, "vitamin_b6_mg": 0.9,
         "vitamin_d_mcg": 12.0, "folate_mcg": 45, "vitamin_e_mg": 3.5,
         "is_vegetarian": False, "is_vegan": False, "is_gluten_free": True,
         "prep_time_min": 15, "cook_time_min": 20},
        {"id": 2, "name": "Lentil Soup with Whole Grain Bread", "cuisine": "Middle Eastern",
         "calories_kcal": 380, "protein_g": 18, "carbohydrate_g": 55, "fat_g": 8,
         "fiber_g": 12, "magnesium_mg": 75, "iron_mg": 6.5,
         "vitamin_c_mg": 8, "folate_mcg": 180, "vitamin_b6_mg": 0.5,
         "vitamin_d_mcg": None, "vitamin_b12_mcg": None, "vitamin_e_mg": None, "omega3_mg": None,
         "is_vegetarian": True, "is_vegan": True, "is_gluten_free": False,
         "prep_time_min": 10, "cook_time_min": 30},
        {"id": 3, "name": "Turkey & Vegetable Stir-fry", "cuisine": "Asian",
         "calories_kcal": 450, "protein_g": 35, "carbohydrate_g": 30, "fat_g": 12,
         "fiber_g": 7, "magnesium_mg": 45, "iron_mg": 3.2,
         "vitamin_c_mg": 45, "vitamin_b12_mcg": 2.8, "vitamin_b6_mg": 1.1,
         "vitamin_d_mcg": 2.5, "folate_mcg": 35, "vitamin_e_mg": 2.1, "omega3_mg": 500,
         "is_vegetarian": False, "is_vegan": False, "is_gluten_free": True,
         "prep_time_min": 15, "cook_time_min": 15},
    ]

    weights    = need.macro_weights
    targets    = {"carb": need.carb_g, "prot": need.prot_g, "fat": need.fat_g}
    priorities = ZONE_MICRONUTRIENT_PRIORITIES.get(zone, [])

    for i, food in enumerate(demo_foods):
        # macro_score
        breakdown = {}
        m_score = 0.0
        for macro, col in (("carb", "carbohydrate_g"), ("prot", "protein_g"), ("fat", "fat_g")):
            actual = float(food.get(col) or 0)
            target = targets[macro]
            ratio  = min(actual / target, 1.0) if target > 0 else 0.0
            w      = weights[macro]
            contrib = round(w * ratio, 4)
            m_score += contrib
            breakdown[macro] = {
                "actual_g": round(actual, 1), "target_g": target,
                "ratio": round(ratio, 3), "contribution": contrib,
            }
        m_score = round(m_score, 6)

        # micro_score (NULL → 0, conservative)
        m_micro = 0.0
        if priorities:
            micro_total = 0.0
            for col in priorities:
                rda_by_sex = RDA_REFERENCE.get(col)
                if rda_by_sex is None:
                    continue
                meal_target = rda_by_sex[sex_key] * meal_fraction
                if meal_target <= 0:
                    continue
                raw_val = food.get(col)
                actual_n = float(raw_val) if raw_val else 0.0
                micro_total += min(actual_n / meal_target, 1.0)
            m_micro = round(micro_total / len(priorities), 6)

        # ENMS — 3-component
        pref = DEFAULT_PREF_SCORE
        enms = round(
            ENMS_MACRO_ALPHA * m_score
            + ENMS_MICRO_BETA  * m_micro
            + pref_weight      * pref,
            6,
        )

        top_macros = sorted(
            ("carb", "prot", "fat"),
            key=lambda m: breakdown[m]["contribution"],
            reverse=True,
        )

        # Micronutrient coverage (informational display)
        micro_covered = []
        for col in priorities:
            rda_by_sex = RDA_REFERENCE.get(col)
            if rda_by_sex is None:
                continue
            meal_target = rda_by_sex[sex_key] * meal_fraction
            val = food.get(col)
            if val is not None:
                micro_covered.append({
                    "nutrient":           col,
                    "label":              NUTRIENT_DISPLAY_LABELS.get(col, col),
                    "actual":             float(val),
                    "meal_target":        round(meal_target, 3),
                    "pct_of_meal_target": round(float(val) / meal_target * 100, 1)
                                          if meal_target > 0 else 0.0,
                })

        food.update({
            "macro_score": m_score, "micro_score": m_micro,
            "macro_breakdown": breakdown,
            "micronutrient_coverage": {"covered": micro_covered, "missing": []},
            "top_macros": top_macros,
            "enms": enms, "final_score": enms, "pref_score": pref,
            "zone": zone, "emotion_V": V, "emotion_A": A,
            "rank": i + 1, "portion_g": 300.0,
            "meal_type": "complete_meal", "category": "dinner",
            "data_completeness": 8, "serving_size_g": 300,
            "ingredients": [], "image_url": None,
            "sugar_g": None, "saturated_fat_g": None,
            "potassium_mg": None, "sodium_mg": None, "zinc_mg": None,
            "calcium_mg": food.get("calcium_mg"), "rating": None,
            "is_dairy_free": False, "complex_carbs_g": food.get("carbohydrate_g"),
        })

    demo_foods.sort(key=lambda f: f["enms"], reverse=True)
    for rank, food in enumerate(demo_foods[:TOP_K_DEFAULT], 1):
        food["rank"] = rank
    return demo_foods[:TOP_K_DEFAULT]


show()
