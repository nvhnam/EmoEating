"""
User profile form: age, sex, height, weight, dietary restrictions, meal type.
Computes BMI/BMR/TDEE on submit and stores in session_state.
"""

from __future__ import annotations

import streamlit as st
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.physiological import compute_profile, profile_to_dict
from utils.formatting import fmt_bmi, bmi_category_color, fmt_kcal
from utils.validation import validate_profile_inputs
from config import MEAL_TYPE_LABELS


def render_profile_form() -> bool:
    """
    Render the profile form. Returns True if submitted successfully.
    Stores results in st.session_state.user_profile and st.session_state.meal_type.
    """
    with st.form("profile_form"):
        col1, col2 = st.columns(2)

        with col1:
            age = st.number_input("Age", min_value=18, max_value=90, step=1, value=30)
            sex = st.selectbox("Biological sex", ["Male", "Female", "Other", "Prefer not to say"])
            height_cm = st.number_input("Height (cm)", min_value=100, max_value=250, step=1, value=170)

        with col2:
            weight_kg = st.number_input("Weight (kg)", min_value=30.0, max_value=300.0, step=0.5, value=70.0)
            meal_type = st.selectbox(
                "Which meal?",
                list(MEAL_TYPE_LABELS.keys()),
                format_func=lambda k: MEAL_TYPE_LABELS[k],
            )
            restrictions = st.multiselect(
                "Dietary restrictions",
                ["Vegetarian", "Vegan", "Gluten-free", "Dairy-free", "Halal", "Kosher", "None"],
                default=[],
            )

        submitted = st.form_submit_button("Save Profile", type="primary")

    if submitted:
        sex_key = sex.lower().replace(" ", "_")
        if sex_key == "prefer_not_to_say":
            sex_key = "other"

        errors = validate_profile_inputs(age, sex_key, height_cm, weight_kg)
        if errors:
            for e in errors:
                st.error(e)
            return False

        profile = compute_profile(age, sex_key, float(height_cm), float(weight_kg))
        st.session_state["user_profile"] = profile_to_dict(profile)
        st.session_state["meal_type"] = meal_type
        st.session_state["dietary_restrictions"] = [r.lower().replace("-", "_") for r in restrictions if r != "None"]

        _display_profile_summary(profile)
        return True

    return False


def _display_profile_summary(profile) -> None:
    """Show compact BMI + caloric target summary after form submission."""
    color = bmi_category_color(profile.bmi_category)
    st.markdown(
        f"""
        <div style="
            background:#f8f9fa; border:1px solid #e2e8f0;
            border-radius:8px; padding:12px 16px; margin-top:12px;
        ">
            <div style="display:flex; gap:24px; flex-wrap:wrap; align-items:center;">
                <div>
                    <span style="font-size:11px; color:#6b7280; display:block;">BMI</span>
                    <span style="font-size:22px; font-weight:700; color:{color};">
                        {fmt_bmi(profile.bmi)}
                    </span>
                    <span style="font-size:11px; color:{color}; margin-left:4px;">
                        {profile.bmi_category.capitalize()}
                    </span>
                </div>
                <div>
                    <span style="font-size:11px; color:#6b7280; display:block;">BMR</span>
                    <span style="font-size:16px; font-weight:600; color:#1a1a2e;">
                        {fmt_kcal(profile.bmr_kcal)}/day
                    </span>
                </div>
                <div>
                    <span style="font-size:11px; color:#6b7280; display:block;">Estimated meal target</span>
                    <span style="font-size:16px; font-weight:600; color:#4a90d9;">
                        ~{fmt_kcal(profile.meal_kcal_target)}
                    </span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "BMI is used as a lightweight proxy for energy estimation in a non-clinical context. "
        "Not a medical diagnosis. (WHO, 2000; Keys et al., 1972)"
    )
