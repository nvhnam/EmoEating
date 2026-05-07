"""
Page 4 — Recommendations (main research output page).
Two-column layout: left context panel | right recommendation cards.
"""

from __future__ import annotations

import streamlit as st
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.affect_mapper import emotion_to_va, get_emotion_metadata
from engine.need_vector import compute_need_vector
from engine.physiological import PhysiologicalProfile
from components.nutrient_bars import render_nutrient_bars
from components.meal_card import render_meal_card
from utils.formatting import fmt_kcal
from config import TOP_K_DEFAULT, MEAL_TYPE_LABELS


def _get_profile() -> PhysiologicalProfile | None:
    pd = st.session_state.get("user_profile")
    if not pd:
        return None
    from engine.physiological import PhysiologicalProfile
    return PhysiologicalProfile(**pd)


def show():
    emotion = st.session_state.get("detected_emotion")
    if not emotion:
        st.warning("No emotion detected. Please go back and select an emotion.")
        if st.button("← Back to Emotion"):
            st.switch_page("pages/03_emotion.py")
        return

    meal_type = st.session_state.get("meal_type", "dinner")
    dietary_restrictions = st.session_state.get("dietary_restrictions", [])
    profile = _get_profile()
    session_token = st.session_state.get("session_token", "anonymous")
    confidence = st.session_state.get("emotion_confidence")

    V, A = emotion_to_va(emotion)
    need = compute_need_vector(V, A)
    meta = get_emotion_metadata(emotion)

    # Run recommendation engine
    if "recommendations" not in st.session_state or st.session_state.get("_reco_emotion") != emotion:
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
                )
                if not recs:
                    st.info(
                        "No meal data loaded yet — showing demo results. "
                        "Run the ETL pipeline to populate real recommendations.",
                        icon=":material/info:",
                    )
                    recs = _demo_recommendations(emotion, need, profile)
                else:
                    try:
                        from db.session_logger import log_recommendation_session
                        sid = log_recommendation_session(
                            session_token=session_token,
                            emotion=emotion,
                            meal_type=meal_type,
                            recommendations=recs,
                            V=V, A=A,
                            confidence=confidence,
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
                recs = _demo_recommendations(emotion, need, profile)

        st.session_state["recommendations"] = recs
        st.session_state["_reco_emotion"] = emotion

    recs = st.session_state.get("recommendations", [])

    # ── Layout ───────────────────────────────────────────────────────────────
    left, right = st.columns([3, 7])

    with left:
        # Emotion context
        st.markdown(
            f"""
            <div style="
                background:#ffffff; border:1px solid #e2e8f0;
                border-radius:8px; padding:16px; margin-bottom:12px;
            ">
                <div style="font-size:2rem;">{meta['emoji']}</div>
                <div style="font-size:1.1rem; font-weight:700; color:#1a1a2e; margin-top:4px;">
                    {emotion.capitalize()}
                </div>
                <div style="font-size:0.8rem; color:#6b7280; margin-top:4px;">
                    V={V:+.2f}, A={A:+.2f}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        render_nutrient_bars(need)

        if profile:
            st.markdown("---")
            st.markdown("**Physiological Profile**")
            st.caption(
                f"BMI: {profile.bmi:.1f} ({profile.bmi_category.capitalize()})\n\n"
                f"Meal target: ~{fmt_kcal(profile.meal_kcal_target)}"
            )

        st.markdown("---")
        if st.button("← Adjust emotion"):
            del st.session_state["recommendations"]
            st.switch_page("pages/03_emotion.py")

    with right:
        meal_label = MEAL_TYPE_LABELS.get(meal_type, meal_type.capitalize())
        st.markdown(
            f"## Recommended for you "
            f'<span style="background:#e8f0fb; color:#4a90d9; '
            f'font-size:0.8rem; padding:3px 10px; border-radius:12px;">'
            f'{meal_label}</span>',
            unsafe_allow_html=True,
        )

        if not recs:
            st.info(
                "No meals found matching your criteria. "
                "Try adjusting your dietary restrictions or meal type."
            )
            return

        meal_kcal_target = profile.meal_kcal_target if profile else None
        session_id = st.session_state.get("session_id")

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


def _demo_recommendations(emotion: str, need, profile) -> list[dict]:
    """
    Fallback demo results when DB is not connected.
    Returns synthetic scored meals for UI demonstration.
    """
    from config import AFFECTIVE_WEIGHT, CALORIC_WEIGHT
    demo_foods = [
        {"id": 1, "name": "Grilled Salmon with Quinoa",       "cuisine": "Mediterranean",
         "calories_kcal": 520, "protein_g": 38, "complex_carbs_g": 42,
         "fiber_g": 5, "omega3_mg": 2000, "magnesium_mg": 60,
         "vitamin_c_mg": 15, "vitamin_b12_mcg": 4.5, "is_vegetarian": False,
         "is_vegan": False, "is_gluten_free": True, "prep_time_min": 15, "cook_time_min": 20},
        {"id": 2, "name": "Lentil Soup with Whole Grain Bread", "cuisine": "Middle Eastern",
         "calories_kcal": 380, "protein_g": 18, "complex_carbs_g": 55,
         "fiber_g": 12, "magnesium_mg": 75, "iron_mg": 6.5,
         "vitamin_c_mg": 8, "folate_mcg": 180, "is_vegetarian": True,
         "is_vegan": True, "is_gluten_free": False, "prep_time_min": 10, "cook_time_min": 30},
        {"id": 3, "name": "Turkey & Vegetable Stir-fry",       "cuisine": "Asian",
         "calories_kcal": 450, "protein_g": 35, "complex_carbs_g": 30,
         "fiber_g": 7, "magnesium_mg": 45, "iron_mg": 3.2,
         "vitamin_c_mg": 45, "vitamin_b12_mcg": 2.8, "is_vegetarian": False,
         "is_vegan": False, "is_gluten_free": True, "prep_time_min": 15, "cook_time_min": 15},
        {"id": 4, "name": "Greek Yogurt Parfait with Berries",  "cuisine": "Western",
         "calories_kcal": 280, "protein_g": 20, "complex_carbs_g": 35,
         "fiber_g": 4, "calcium_mg": 300, "vitamin_c_mg": 30,
         "vitamin_b12_mcg": 1.2, "is_vegetarian": True,
         "is_vegan": False, "is_gluten_free": True, "prep_time_min": 5, "cook_time_min": 0},
        {"id": 5, "name": "Black Bean Burrito Bowl",           "cuisine": "Mexican",
         "calories_kcal": 480, "protein_g": 22, "complex_carbs_g": 60,
         "fiber_g": 15, "magnesium_mg": 80, "iron_mg": 5.0,
         "folate_mcg": 200, "vitamin_c_mg": 25, "is_vegetarian": True,
         "is_vegan": True, "is_gluten_free": True, "prep_time_min": 10, "cook_time_min": 15},
    ]

    import random
    for i, food in enumerate(demo_foods):
        food["affective_score"] = round(0.75 - i * 0.05 + random.uniform(-0.03, 0.03), 4)
        food["top_contributors"] = ["Protein", "Magnesium", "B Vitamins"][:3 - (i % 2)]
        food["caloric_proximity_score"] = None
        food["final_score"] = food["affective_score"]
        food["rank"] = i + 1
        food.setdefault("tryptophan_mg", None)
        food.setdefault("omega3_mg", None)
        food.setdefault("vitamin_e_mg", None)
        food.setdefault("sugar_g", None)
        food.setdefault("fat_g", None)
        food.setdefault("serving_size_g", None)
        food.setdefault("rating", None)
        food.setdefault("data_completeness", 7)
        food.setdefault("meal_type", "complete_meal")
        food.setdefault("category", "dinner")
        food.setdefault("is_dairy_free", False)
        food.setdefault("carbohydrate_g", food.get("complex_carbs_g", 0))
        food.setdefault("saturated_fat_g", None)
        food.setdefault("prep_time_min", 15)
        food.setdefault("cook_time_min", 20)
        food.setdefault("folate_mcg", None)
        food.setdefault("potassium_mg", None)
        food.setdefault("sodium_mg", None)
        food.setdefault("zinc_mg", None)
        food.setdefault("calcium_mg", None)
        food.setdefault("magnesium_mg", None)
        food.setdefault("iron_mg", None)
        food.setdefault("vitamin_c_mg", None)
        food.setdefault("vitamin_b12_mcg", None)
        food.setdefault("ingredients", [])

    return demo_foods

show()
