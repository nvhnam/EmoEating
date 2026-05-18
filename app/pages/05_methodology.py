"""
Page 5 — Methodology (research transparency).
Documents the 5-stage ENMS pipeline with live demo and full citations.
"""

from __future__ import annotations

import streamlit as st
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from config import (
    EMOTION_COORDS, ZONE_LABELS, ZONE_COLORS,
    ZONE_MACRO_RATIOS, ZONE_MACRO_WEIGHTS,
    ZONE_MICRONUTRIENT_PRIORITIES, RDA_REFERENCE,
    NUTRIENT_DISPLAY_LABELS, MEAL_ENERGY_FRACTION,
    DEFAULT_MEAL_KCAL, THETA_NEUTRAL, ENMS_ALPHA,
    DEFAULT_PREF_SCORE, TOP_K_DEFAULT,
)


def show():
    st.title("Methodology")
    st.markdown(
        "This page documents the computational pipeline underpinning MoodMeal's "
        "recommendations for research transparency and reviewer access. "
        "The system implements a 5-stage **Emotion-Nutrition Matching Score (ENMS)** pipeline "
        "grounded in peer-reviewed nutritional neuroscience and affective computing research."
    )

    # ── 1. Emotion Detection ─────────────────────────────────────────────────
    with st.expander("Stage 1 — Emotion Detection", expanded=True):
        st.markdown(
            "Voice-based emotion detection is pending integration. The system currently "
            "accepts a user-selected emotion label from **11 predefined classes** based on "
            "the Ekman (1992) taxonomy of acute, event-triggered emotions."
        )
        st.caption(
            "Ekman, P. (1992). An argument for basic emotions. "
            "_Cognition & Emotion_, 6(3–4), 169–200."
        )

    # ── 2. Dimensional Affect Mapping ────────────────────────────────────────
    with st.expander("Stage 2 — Dimensional Affect Mapping (Russell Circumplex)", expanded=True):
        st.markdown(
            "Each emotion label is mapped to a **(Valence, Arousal)** coordinate pair "
            "using the Russell Circumplex Model of Affect (1980). "
            "Valence ∈ [−1, +1] represents hedonic tone (negative ↔ positive). "
            "Arousal ∈ [−1, +1] represents activation level (calm ↔ excited)."
        )
        st.latex(r"\text{emotion} \xrightarrow{\text{Table 1}} (V,\, A) \in [-1,\, 1]^2")

        rows = [
            (m["emoji"], e.capitalize(), round(m["V"], 2), round(m["A"], 2))
            for e, m in EMOTION_COORDS.items()
        ]
        df = pd.DataFrame(rows, columns=["", "Emotion", "Valence (V)", "Arousal (A)"])
        st.dataframe(df, hide_index=True, use_container_width=True)

        st.caption(
            "Russell, J. A. (1980). A circumplex model of affect. "
            "_Journal of Personality and Social Psychology_, 39(6), 1161–1178.\n\n"
            "Posner, J., Russell, J. A., & Peterson, B. S. (2005). "
            "_Development and Psychopathology_, 17(3), 715–734."
        )

    # ── 3. Zone Classification ───────────────────────────────────────────────
    with st.expander("Stage 2b — Emotional Zone Classification", expanded=True):
        st.markdown(
            "The (V, A) point is classified into one of **five emotional zones** using "
            "quadrant rules on the Russell Circumplex. "
            f"A neutral dead-zone threshold θ = **{THETA_NEUTRAL}** is applied: "
            "points within Euclidean distance θ of the origin map to NEUTRAL."
        )
        st.latex(
            r"\text{Zone}(V, A) = \begin{cases}"
            r"\text{NEUTRAL} & \text{if } \sqrt{V^2 + A^2} < \theta \\"
            r"\text{Q2\_STRESSED} & V \le 0,\; A \ge 0 \\"
            r"\text{Q3\_FATIGUED} & V \le 0,\; A < 0 \\"
            r"\text{Q1\_HAPPY} & V > 0,\; A \ge 0 \\"
            r"\text{Q4\_CONTENT} & V > 0,\; A < 0"
            r"\end{cases}"
        )

        zone_rows = [
            (z, ZONE_LABELS[z], "V>0, A≥0" if z == "Q1_HAPPY"
             else "V≤0, A≥0" if z == "Q2_STRESSED"
             else "V≤0, A<0" if z == "Q3_FATIGUED"
             else "V>0, A<0" if z == "Q4_CONTENT"
             else f"||V,A|| < {THETA_NEUTRAL}")
            for z in ["Q1_HAPPY", "Q2_STRESSED", "Q3_FATIGUED", "Q4_CONTENT", "NEUTRAL"]
        ]
        df_z = pd.DataFrame(zone_rows, columns=["Zone ID", "Label", "Quadrant Rule"])
        st.dataframe(df_z, hide_index=True, use_container_width=True)

        st.markdown("**Live demo — emotion → zone:**")
        from engine.affect_mapper import emotion_to_va
        from engine.zone_classifier import classify_zone
        demo_emo_z = st.selectbox(
            "Select emotion", list(EMOTION_COORDS.keys()), key="method_demo_zone"
        )
        if demo_emo_z:
            _V, _A = emotion_to_va(demo_emo_z)
            _zone = classify_zone(_V, _A)
            _color = ZONE_COLORS.get(_zone, "#888780")
            _label = ZONE_LABELS.get(_zone, _zone)
            st.markdown(
                f'<span style="background:{_color}22; color:{_color}; '
                f'border:1px solid {_color}; font-size:12px; font-weight:700; '
                f'padding:4px 12px; border-radius:12px;">'
                f'Zone: {_label}</span> '
                f'<span style="font-size:11px; color:#6b7280; margin-left:8px;">'
                f'V={_V:+.2f}, A={_A:+.2f}</span>',
                unsafe_allow_html=True,
            )

        st.caption(
            "Design parameter θ = 0.25 based on output distribution of the "
            "self-reported emotion validation set. See formula_plan.md §2."
        )

    # ── 4. Nutritional Need Vector ───────────────────────────────────────────
    with st.expander("Stage 3 — Nutritional Need Vector (NNV)", expanded=True):
        st.markdown(
            "Each zone maps to a **macro-nutrient ratio profile** grounded in the "
            "USDA Acceptable Macronutrient Distribution Ranges (AMDR). "
            "Gram targets are derived from the per-meal energy budget:"
        )
        st.latex(
            r"\text{carb}_g = \frac{p_\text{carb} \times E_\text{meal}}{4 \;\text{kcal/g}}, \quad"
            r"\text{prot}_g = \frac{p_\text{prot} \times E_\text{meal}}{4 \;\text{kcal/g}}, \quad"
            r"\text{fat}_g  = \frac{p_\text{fat}  \times E_\text{meal}}{9 \;\text{kcal/g}}"
        )
        st.markdown(
            f"Where *E*_meal = TDEE × meal-type fraction "
            f"(breakfast 25%, lunch 35%, dinner 30%, snack 10%). "
            f"Default *E*_meal = **{DEFAULT_MEAL_KCAL} kcal** when no physiological profile is provided."
        )

        ratio_rows = [
            (ZONE_LABELS[z],
             f"{int(ZONE_MACRO_RATIOS[z]['carb']*100)}%",
             f"{int(ZONE_MACRO_RATIOS[z]['prot']*100)}%",
             f"{int(ZONE_MACRO_RATIOS[z]['fat']*100)}%",
             f"{ZONE_MACRO_WEIGHTS[z]['carb']:.2f}",
             f"{ZONE_MACRO_WEIGHTS[z]['prot']:.2f}",
             f"{ZONE_MACRO_WEIGHTS[z]['fat']:.2f}")
            for z in ["Q1_HAPPY", "Q2_STRESSED", "Q3_FATIGUED", "Q4_CONTENT", "NEUTRAL"]
        ]
        df_r = pd.DataFrame(
            ratio_rows,
            columns=["Zone", "Carb %", "Protein %", "Fat %", "w_carb", "w_prot", "w_fat"],
        )
        st.dataframe(df_r, hide_index=True, use_container_width=True)
        st.caption(
            "Macro ratios within USDA AMDR bounds (carb 45–65%, protein 10–35%, fat 20–35%). "
            "Zone-specific biases grounded in: Wurtman & Wurtman (1995) — carb/serotonin; "
            "Young (2007) — protein/dopamine; Grosso et al. (2014) — fat/mood."
        )

        st.markdown("**Live demo — emotion + meal type → NNV:**")
        from engine.need_vector import compute_need_vector
        from components.nutrient_bars import render_macro_targets
        _col1, _col2 = st.columns(2)
        with _col1:
            demo_emo_n = st.selectbox(
                "Emotion", list(EMOTION_COORDS.keys()), key="method_demo_nnv"
            )
        with _col2:
            demo_meal_n = st.selectbox(
                "Meal type", list(MEAL_ENERGY_FRACTION.keys()), key="method_demo_meal"
            )
        if demo_emo_n:
            _Vn, _An = emotion_to_va(demo_emo_n)
            _zn = classify_zone(_Vn, _An)
            _frac = MEAL_ENERGY_FRACTION.get(demo_meal_n, 1 / 3)
            _kcal = round(DEFAULT_MEAL_KCAL * _frac / (1 / 3))
            _need = compute_need_vector(_zn, _kcal)
            render_macro_targets(_need)

    # ── 5. ENMS Scoring ──────────────────────────────────────────────────────
    with st.expander("Stage 4 — ENMS Macro Fulfillment Scoring", expanded=True):
        st.markdown(
            "The **Emotion-Nutrition Matching Score (ENMS)** blends macro fulfillment "
            "with a preference prior:"
        )
        st.latex(
            r"\text{ENMS}(f, Z, U) = \alpha \cdot \text{macro\_score}(f, Z, U)"
            r"+ (1 - \alpha) \cdot \text{pref\_score}(f, U)"
        )
        st.markdown("**Macro fulfillment score** (portion-adjusted):")
        st.latex(
            r"\text{macro\_score} = \sum_{m \in \{carb,\, prot,\, fat\}}"
            r"w_m^{Zone} \cdot \min\!\left(\frac{n_m^{actual}}{n_m^{target}},\; 1\right)"
        )
        st.latex(
            r"n_m^{actual} = \frac{n_m^{per\,100g} \times \text{portion}_g}{100}"
        )
        st.markdown(
            "Each ratio is **capped at 1.0** to prevent over-fulfillment from dominating the score. "
            "Weights w_m^Zone sum to 1.0 per zone (see Stage 3 table). "
            "NULL macro values are treated as 0 (conservative; not imputed)."
        )

        params = [
            ("α (ENMS_ALPHA)", ENMS_ALPHA, "Macro score weight; 70% nutritional signal"),
            ("pref_score", DEFAULT_PREF_SCORE, "Neutral preference prior (no user history yet)"),
            ("θ_neutral", THETA_NEUTRAL, "Russell circumplex neutral dead-zone radius"),
            ("TOP_K", TOP_K_DEFAULT, "Recommendations returned per query"),
            ("DEFAULT_MEAL_KCAL", DEFAULT_MEAL_KCAL, "Profile-free meal energy fallback (kcal)"),
            ("Portion (main)", 300, "Default serving size for main dishes (g)"),
            ("Portion (soup/stew)", 250, "Default serving size for soups/stews (g)"),
        ]
        df_p = pd.DataFrame(params, columns=["Parameter", "Value", "Justification"])
        st.dataframe(df_p, hide_index=True, use_container_width=True)

        st.markdown(
            f"**ENMS range:** [{ENMS_ALPHA * 0 + (1-ENMS_ALPHA) * DEFAULT_PREF_SCORE:.2f}, "
            f"{ENMS_ALPHA * 1 + (1-ENMS_ALPHA) * DEFAULT_PREF_SCORE:.2f}] "
            "when pref_score = 0.5 (neutral prior)."
        )
        st.caption(
            "Portion defaults: main_dish=300g, side_dish=150g, soup/stew=250g, salad=200g. "
            "Fallback uses food's serving_size_g if available, else 300g."
        )

    # ── 6. Micronutrient Informational Display ───────────────────────────────
    with st.expander("Stage 5 — Micronutrient Informational Display", expanded=False):
        st.markdown(
            "**Micronutrients are NOT part of the ENMS score.** "
            "They serve as whole-diet guidance — the system surfaces zone-specific "
            "micronutrient priorities to help users understand their nutritional needs, "
            "but these have zero effect on food ranking."
        )
        st.info(
            "**Data limitation:** Many foods in the USDA corpus have incomplete "
            "micronutrient records. NULL or zero values are silently skipped — they do not "
            "penalise or boost a food's ENMS score. A high ENMS score reflects good "
            "macro fulfillment, not micronutrient completeness.",
            icon=":material/info:",
        )

        micro_rows = []
        for z in ["Q1_HAPPY", "Q2_STRESSED", "Q3_FATIGUED", "Q4_CONTENT", "NEUTRAL"]:
            priorities = ZONE_MICRONUTRIENT_PRIORITIES.get(z, [])
            rda_strs = []
            for col in priorities:
                label = NUTRIENT_DISPLAY_LABELS.get(col, col)
                rda = RDA_REFERENCE.get(col)
                if rda:
                    unit = "µg" if col.endswith("_mcg") else ("g" if col.endswith("_g") else "mg")
                    rda_strs.append(f"{label} ({rda['male']}{unit}/day)")
                else:
                    rda_strs.append(label)
            micro_rows.append((ZONE_LABELS[z], ", ".join(rda_strs) or "—"))
        df_m = pd.DataFrame(micro_rows, columns=["Zone", "Priority Micronutrients (RDA/day, male)"])
        st.dataframe(df_m, hide_index=True, use_container_width=True)

        st.caption(
            "RDA values: NIH Office of Dietary Supplements, Dietary Reference Intakes (2020). "
            "Omega-3 values are Adequate Intake (AI) levels. "
            "Zone priorities grounded in: Boyle et al. (2017) — Mg/stress; "
            "Kennedy (2016) — B vitamins; Jacka et al. (2017) — dietary patterns and depression."
        )

    # ── 7. Physiological Profile Adaptation ─────────────────────────────────
    with st.expander("Stage 1b — Physiological Profile Adaptation", expanded=False):
        st.markdown("**Mifflin-St Jeor BMR equation (1990) — current clinical standard:**")
        st.latex(
            r"\text{BMR}_{\text{male}} = 10w + 6.25h - 5a + 5 \quad [\text{kcal/day}]"
        )
        st.latex(
            r"\text{BMR}_{\text{female}} = 10w + 6.25h - 5a - 161 \quad [\text{kcal/day}]"
        )
        st.latex(
            r"\text{TDEE} = \text{BMR} \times \phi \qquad"
            r"\phi \in \{1.2,\; 1.375,\; 1.55\}"
        )
        st.markdown(
            "Activity multipliers φ: Sedentary = 1.2, Lightly Active = 1.375, "
            "Moderately Active = 1.55 (USDA Dietary Guidelines 2020–2025)."
        )
        st.latex(
            r"E_{\text{meal}} = \text{TDEE} \times f_{\text{meal}}"
        )
        meal_frac_rows = [(k.capitalize(), f"{int(v*100)}%")
                          for k, v in MEAL_ENERGY_FRACTION.items()]
        df_mf = pd.DataFrame(meal_frac_rows, columns=["Meal Type", "Fraction of TDEE"])
        st.dataframe(df_mf, hide_index=True, use_container_width=True)
        st.markdown(
            f"When no profile is provided, *E*_meal defaults to **{DEFAULT_MEAL_KCAL} kcal** "
            "(design parameter; documented in paper)."
        )
        st.caption(
            "Mifflin et al. (1990). _American Journal of Clinical Nutrition_, 51(2), 241–247.\n\n"
            "USDA (2020). _Dietary Guidelines for Americans 2020–2025_, 9th Edition."
        )

    # ── 8. Database Corpus ───────────────────────────────────────────────────
    with st.expander("Appendix — Meal Database", expanded=False):
        st.markdown(
            "The meal corpus is assembled from five publicly available datasets:\n\n"
            "| Source | Dataset | Approx. Size |\n"
            "|--------|---------|------|\n"
            "| Food.com | RAW_recipes | ~231,637 recipes |\n"
            "| USDA Nutritional DB | nutrition.csv | ~8,789 foods |\n"
            "| Open Food Facts | products.tsv | filtered subset |\n"
            "| Epicurious | epi_r.csv | ~20,000 recipes |\n"
            "| Vietnamese Food | vietnamese_food.csv | regional diversity |\n\n"
            "**Quality filters:** calories > 50 kcal, protein > 2g, "
            "data_completeness ≥ 5 mood-relevant nutrients, "
            "prep+cook time < 120 min."
        )
        try:
            from db.connection import test_connection
            from db.queries import get_corpus_stats
            if test_connection():
                stats = get_corpus_stats()
                st.dataframe(pd.DataFrame(stats), hide_index=True, use_container_width=True)
        except Exception:
            st.caption("Database not connected — corpus statistics unavailable.")

    # ── 9. References ─────────────────────────────────────────────────────────
    with st.expander("Full Reference List", expanded=False):
        refs = [
            "Ekman, P. (1992). An argument for basic emotions. *Cognition & Emotion*, 6(3–4), 169–200.",
            "Russell, J. A. (1980). A circumplex model of affect. *Journal of Personality and Social Psychology*, 39(6), 1161–1178.",
            "Posner, J., Russell, J. A., & Peterson, B. S. (2005). The circumplex model of affect. *Development and Psychopathology*, 17(3), 715–734.",
            "Mifflin, M. D., et al. (1990). A new predictive equation for resting energy expenditure. *American Journal of Clinical Nutrition*, 51(2), 241–247.",
            "USDA (2020). *Dietary Guidelines for Americans 2020–2025*, 9th Edition.",
            "NIH Office of Dietary Supplements (2020). *Dietary Reference Intakes (DRI)*. National Institutes of Health.",
            "Wurtman, R. J., & Wurtman, J. J. (1995). Brain serotonin, carbohydrate-craving, obesity and depression. *Obesity Research*, 3(S4), 477S–480S.",
            "Young, S. N. (2007). How to increase serotonin in the human brain without drugs. *Journal of Psychiatry & Neuroscience*, 32(6), 394–399.",
            "Grosso, G. et al. (2014). Role of omega-3 fatty acids in the treatment of depressive disorders. *PLOS ONE*, 9(5).",
            "Boyle, N. B., Lawton, C., & Dye, L. (2017). The effects of magnesium supplementation on subjective anxiety and stress. *Nutrients*, 9(5), 429.",
            "Kennedy, D. O. (2016). B vitamins and the brain. *Nutrients*, 8(2), 68.",
            "Jacka, F. N., et al. (2017). A randomised controlled trial of dietary improvement for adults with major depression. *BMC Medicine*, 15, 23.",
            "Lopresti, A. L. (2020). The effects of psychological and environmental stress on micronutrient concentrations in the body. *Advances in Nutrition*, 11(1), 103–112.",
            "Cryan, J. F., et al. (2019). The microbiota-gut-brain axis. *Physiological Reviews*, 99(4), 1877–2013.",
            "Macht, M. (2008). How emotions affect eating. *Appetite*, 50(1), 1–11.",
            "Gangwisch, J. E., et al. (2015). High glycemic index diet as a risk factor for depression. *American Journal of Clinical Nutrition*, 102(2), 454–463.",
            "WHO (2000). *Obesity: preventing and managing the global epidemic*. Report of a WHO Consultation.",
        ]
        for i, ref in enumerate(refs, 1):
            st.markdown(f"{i}. {ref}")


show()
