"""
Page 5 — Methodology (research transparency).
Documents the ENMS pipeline with live demo and full citations.
Aligned with guide.md specification for UIST 2026 submission.
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
    DEFAULT_MEAL_KCAL, THETA_NEUTRAL,
    ENMS_MACRO_ALPHA, ENMS_MICRO_BETA,
    DEFAULT_PREF_SCORE, TOP_K_DEFAULT,
    SER_MODEL_ID, SER_EMOTION_TO_ZONE,
)


def show():
    st.title("Methodology")
    st.markdown(
        "This page documents the computational pipeline underpinning MoodMeal's "
        "recommendations for research transparency and reviewer access. "
        "The system implements the **Emotion-Nutrition Matching Score (ENMS)** pipeline "
        "grounded in peer-reviewed nutritional neuroscience and affective computing research."
    )
    st.info(
        "**UIST 2026 framing:** The ENMS composite formula is the system's design contribution. "
        "The components (AMDR bounds, TDEE formula, per-zone micronutrient priorities, NIH RDAs) "
        "are grounded in published research; the weighted aggregation is the authors' contribution. "
        "α, β, γ are design parameters; empirical calibration is identified as future work.",
        icon=":material/science:",
    )

    # ── Stage 1 — SER ────────────────────────────────────────────────────────
    with st.expander("Stage 1 — Speech Emotion Recognition (SER)", expanded=True):
        st.markdown(
            f"Voice emotion detection uses **`{SER_MODEL_ID}`** off-the-shelf via FunASR "
            f"`AutoModel` (no fine-tuning, no ensembling — guide.md Phase 1). "
            f"Single-pass inference: 16 kHz mono WAV → 9-class softmax → argmax → zone lookup."
        )
        st.markdown(
            "**Why emotion2vec_plus_large:**\n"
            "- Published in **Findings of ACL 2024** (peer-reviewed top-tier NLP venue).\n"
            "- Fine-tuned on **42,526 hours** of pseudo-labelled emotion speech.\n"
            "- Documented cross-lingual generalisation across 10 languages."
        )

        ser_rows = [(emo.capitalize(), ZONE_LABELS.get(z, z), z)
                    for emo, z in SER_EMOTION_TO_ZONE.items()]
        df_ser = pd.DataFrame(ser_rows, columns=["SER Emotion Class", "Zone Label", "Zone ID"])
        st.dataframe(df_ser, hide_index=True, use_container_width=True)

        st.markdown(
            "The SER module returns **both the assigned zone AND the raw 9-class probability "
            "vector** for confusion-matrix reporting and low-confidence-case analysis (§7.1). "
            "Manual emotion selection (11-emotion grid) is also available as a fallback."
        )
        st.caption(
            "Ma, Z., et al. (2024). emotion2vec: Self-Supervised Pre-Training for Speech Emotion "
            "Representation. *Findings of ACL 2024*, 15747–15760. "
            "DOI: 10.18653/v1/2024.findings-acl.931\n\n"
            "User-study prompt: RAVDESS standardised sentences "
            "(\"Kids are talking by the door.\"), read twice. "
            "Livingstone & Russo (2018). *PLOS ONE*, 13(5), e0196391. "
            "DOI: 10.1371/journal.pone.0196391"
        )

    # ── Stage 2 — Dimensional Affect Mapping ─────────────────────────────────
    with st.expander("Stage 2 — Dimensional Affect Mapping (Russell Circumplex)", expanded=True):
        st.markdown(
            "For the manual-selection path, each emotion label maps to a **(Valence, Arousal)** "
            "coordinate pair using the Russell Circumplex Model of Affect (1980). "
            "Valence ∈ [−1, +1] represents hedonic tone; Arousal ∈ [−1, +1] represents activation. "
            "The SER path bypasses this table — zone is assigned directly from the 9-class lookup."
        )
        st.latex(r"\text{emotion} \xrightarrow{\text{Table}} (V,\, A) \in [-1,\, 1]^2")

        rows = [
            (m["emoji"], e.capitalize(), round(m["V"], 2), round(m["A"], 2))
            for e, m in EMOTION_COORDS.items()
        ]
        df = pd.DataFrame(rows, columns=["", "Emotion", "Valence (V)", "Arousal (A)"])
        st.dataframe(df, hide_index=True, use_container_width=True)

        st.caption(
            "Russell, J. A. (1980). A circumplex model of affect. "
            "*Journal of Personality and Social Psychology*, 39(6), 1161–1178.\n\n"
            "Posner, J., Russell, J. A., & Peterson, B. S. (2005). "
            "*Development and Psychopathology*, 17(3), 715–734. "
            "DOI: 10.1017/S0954579405050340"
        )

    # ── Stage 2b — Zone Classification ───────────────────────────────────────
    with st.expander("Stage 2b — Emotional Zone Classification (4-zone model)", expanded=True):
        st.markdown(
            f"The (V, A) point is classified into one of **4 emotional zones** (guide.md Phase 2). "
            f"A neutral dead-zone threshold θ = **{THETA_NEUTRAL}** is applied: "
            f"points within Euclidean distance θ of the origin map to NEUTRAL_BASELINE. "
            f"The prior Q4 (positive deactivation / calm) is **merged into NEUTRAL_BASELINE** — "
            f"valence at low arousal is the least recoverable affective dimension from "
            f"prosody-only SER (Posner, Russell & Peterson 2005)."
        )
        st.latex(
            r"\text{Zone}(V, A) = \begin{cases}"
            r"\text{NEUTRAL\_BASELINE} & \text{if } \sqrt{V^2 + A^2} < \theta \\"
            r"\text{Q2\_NEG\_ACT} & V \le 0,\; A \ge 0 \\"
            r"\text{Q3\_NEG\_DEACT} & V \le 0,\; A < 0 \\"
            r"\text{Q1\_POS\_ACT} & V > 0,\; A \ge 0 \\"
            r"\text{NEUTRAL\_BASELINE} & V > 0,\; A < 0 \quad \text{(Q4 merged)}"
            r"\end{cases}"
        )

        zone_rows = [
            ("Q1_POS_ACT",       ZONE_LABELS["Q1_POS_ACT"],       "+V, +A"),
            ("Q2_NEG_ACT",       ZONE_LABELS["Q2_NEG_ACT"],       "−V, +A"),
            ("Q3_NEG_DEACT",     ZONE_LABELS["Q3_NEG_DEACT"],     "−V, −A"),
            ("NEUTRAL_BASELINE", ZONE_LABELS["NEUTRAL_BASELINE"],
             f"||V,A|| < {THETA_NEUTRAL}  OR  +V, −A (Q4 merged)"),
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
            _zone  = classify_zone(_V, _A)
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
            "self-reported emotion validation set. See guide.md Phase 2."
        )

    # ── Stage 3 — Physiological / TDEE ───────────────────────────────────────
    with st.expander("Stage 1b — Physiological Profile Adaptation (TDEE)", expanded=False):
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
            "Activity multipliers φ: Sedentary = 1.2 **(default)**, Lightly Active = 1.375, "
            "Moderately Active = 1.55 (USDA Dietary Guidelines 2020–2025)."
        )
        st.latex(r"E_{\text{meal}} = \text{TDEE} \times f_{\text{meal}}")
        meal_frac_rows = [(k.capitalize(), f"{int(v*100)}%")
                          for k, v in MEAL_ENERGY_FRACTION.items()]
        df_mf = pd.DataFrame(meal_frac_rows, columns=["Meal Type", "Fraction of TDEE"])
        st.dataframe(df_mf, hide_index=True, use_container_width=True)
        st.markdown(
            f"When no profile is provided, *E*_meal defaults to **{DEFAULT_MEAL_KCAL} kcal** "
            "(design parameter; documented in paper)."
        )
        st.caption(
            "Mifflin, M. D., et al. (1990). *American Journal of Clinical Nutrition*, 51(2), 241–247. "
            "PMID: 2305711.\n\n"
            "USDA (2020). *Dietary Guidelines for Americans 2020–2025*, 9th Edition."
        )

    # ── Stage 3 — NNV ─────────────────────────────────────────────────────────
    with st.expander("Stage 3 — Nutritional Need Vector (NNV)", expanded=True):
        st.markdown(
            "Each zone maps to a **macro-nutrient ratio profile** within USDA AMDR bounds "
            "(carb 45–65%, protein 10–35%, fat 20–35%). "
            "Zone-specific positioning is a *design choice motivated by cited mechanisms* — "
            "NOT a quoted prescription from any single paper. State this explicitly in the paper."
        )
        st.latex(
            r"\text{carb}_g = \frac{p_\text{carb} \times E_\text{meal}}{4 \;\text{kcal/g}}, \quad"
            r"\text{prot}_g = \frac{p_\text{prot} \times E_\text{meal}}{4 \;\text{kcal/g}}, \quad"
            r"\text{fat}_g  = \frac{p_\text{fat}  \times E_\text{meal}}{9 \;\text{kcal/g}}"
        )

        ratio_rows = [
            (ZONE_LABELS[z],
             f"{int(ZONE_MACRO_RATIOS[z]['carb']*100)}%",
             f"{int(ZONE_MACRO_RATIOS[z]['prot']*100)}%",
             f"{int(ZONE_MACRO_RATIOS[z]['fat']*100)}%",
             f"{ZONE_MACRO_WEIGHTS[z]['carb']:.2f}",
             f"{ZONE_MACRO_WEIGHTS[z]['prot']:.2f}",
             f"{ZONE_MACRO_WEIGHTS[z]['fat']:.2f}",
             _zone_mechanism(z))
            for z in ["Q1_POS_ACT", "Q2_NEG_ACT", "Q3_NEG_DEACT", "NEUTRAL_BASELINE"]
        ]
        df_r = pd.DataFrame(
            ratio_rows,
            columns=["Zone", "Carb %", "Protein %", "Fat %", "w_carb", "w_prot", "w_fat", "Mechanism (cite)"],
        )
        st.dataframe(df_r, hide_index=True, use_container_width=True)
        st.caption(
            "All ratios within USDA AMDR bounds. Zone biases: "
            "Macht (2008) — Q1 emotion-eating; Wurtman & Wurtman (1995) — Q2 carb/serotonin; "
            "Benton (2002) — Q3 blood glucose/mood; Gómez-Pinilla (2008) — omega-3/BDNF; "
            "Jacka et al. (2017 SMILES) — NEUTRAL Mediterranean pattern."
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
            _zn   = classify_zone(_Vn, _An)
            _frac = MEAL_ENERGY_FRACTION.get(demo_meal_n, 1 / 3)
            _kcal = round(DEFAULT_MEAL_KCAL * _frac / (1 / 3))
            _need = compute_need_vector(_zn, _kcal)
            render_macro_targets(_need)

    # ── Stage 4 — ENMS Scoring ─────────────────────────────────────────────────
    with st.expander("Stage 4 — ENMS Hybrid Scoring (3-Component)", expanded=True):
        st.markdown(
            "The **Emotion-Nutrition Matching Score (ENMS)** is the system's design "
            "contribution. It blends three components into a computable food ranking:"
        )
        st.latex(
            r"\text{ENMS}(f, Z, U) = \alpha \cdot \text{macro\_score}(f, Z, U)"
            r"+ \beta \cdot \text{micro\_score}(f, Z, U)"
            r"+ \gamma \cdot \text{pref\_score}(f, U)"
        )
        st.markdown(
            r"where $\alpha + \beta + \gamma = 1$, with "
            rf"$\alpha = {ENMS_MACRO_ALPHA}$, $\beta = {ENMS_MICRO_BETA}$, "
            rf"$\gamma = {round(1 - ENMS_MACRO_ALPHA - ENMS_MICRO_BETA, 2)}$."
        )
        st.info(
            "**Design intuition:** Macros (α=0.55) anchor energy balance — the AMDR "
            "distinction between zones is moderate. Micronutrients (β=0.20) carry the "
            "*zone-specific affective signal* — sharpest differentiator between zones, "
            "but weighted lower due to empirically inconsistent food-database coverage. "
            "Preference (γ=0.25) preserves user agency and prevents the recommender "
            "from feeling clinical.",
            icon=":material/info:",
        )

        st.markdown("**Step C — macro_score** (cap at 1 per macro; exceeding target = no extra credit):")
        st.latex(
            r"\text{macro\_score} = \sum_{m \in \{carb,\, prot,\, fat\}}"
            r"w_m^{Zone} \cdot \min\!\left(\frac{n_m^{actual}}{n_m^{target}},\; 1\right)"
        )
        st.latex(
            r"n_m^{actual} = \frac{n_m^{per\,100g} \times \text{portion}_g}{100}"
        )

        st.markdown("**Step D — micro_score** (zone-priority micronutrients; NULL → 0, no skip-renormalise):")
        st.latex(
            r"\text{micro\_score} = \frac{1}{|N_Z|} \sum_{n \in N_Z}"
            r"\min\!\left(\frac{a_n(f,\,U)}{t_n(U)},\; 1\right)"
        )
        st.latex(
            r"a_n(f,U) = \frac{\text{food}[n] \times \text{portion}_g}{100}, \quad"
            r"t_n(U) = \text{RDA}[n][\text{sex}] \times f_{\text{meal}}"
        )
        st.markdown(
            r"Every zone has $|N_Z| \geq 2$ (guide.md Phase 4.2) — score is always well-defined. "
            r"NULL → 0 (conservative rule — avoids score gaming by partial reporters). "
            r"The β=0.20 weight ceiling limits the NULL-penalty to at most 0.20 of ENMS."
        )

        _pref_w = round(1 - ENMS_MACRO_ALPHA - ENMS_MICRO_BETA, 2)
        _lo = round(ENMS_MACRO_ALPHA * 0 + ENMS_MICRO_BETA * 0 + _pref_w * DEFAULT_PREF_SCORE, 3)
        _hi = round(ENMS_MACRO_ALPHA * 1 + ENMS_MICRO_BETA * 1 + _pref_w * DEFAULT_PREF_SCORE, 3)

        params = [
            ("α (ENMS_MACRO_ALPHA)",  ENMS_MACRO_ALPHA,  "Macro fulfillment weight"),
            ("β (ENMS_MICRO_BETA)",   ENMS_MICRO_BETA,   "Zone-priority micro fulfillment weight"),
            ("γ (pref weight)",       _pref_w,           "Preference prior weight (1 − α − β)"),
            ("pref_score",            DEFAULT_PREF_SCORE, "Neutral prior — no user history yet"),
            ("θ_neutral",             THETA_NEUTRAL,     "Circumplex neutral dead-zone radius"),
            ("TOP_K",                 TOP_K_DEFAULT,     "Recommendations returned per query"),
            ("DEFAULT_MEAL_KCAL",     DEFAULT_MEAL_KCAL, "Profile-free meal energy fallback (kcal)"),
            ("Portion (main_dish)",   300,               "Default serving size (g)"),
            ("Portion (soup/stew)",   250,               "Default serving size (g)"),
        ]
        df_p = pd.DataFrame(params, columns=["Parameter", "Value", "Justification"])
        st.dataframe(df_p, hide_index=True, use_container_width=True)
        st.markdown(
            f"**ENMS range:** [{_lo}, {_hi}] when pref_score = {DEFAULT_PREF_SCORE} (neutral prior)."
        )

    # ── Stage 5 — Zone-Priority Micronutrients ────────────────────────────────
    with st.expander("Stage 5 — Zone-Priority Micronutrient Scoring (N_Z)", expanded=False):
        st.markdown(
            "Zone-priority micronutrients are **scored in the β=0.20 component** of ENMS. "
            "Every zone now has |N_Z| ≥ 2 (guide.md Phase 4.2) — no zone has an empty set. "
            "Focused lists create stronger discrimination signal; each list reflects the "
            "neurochemical mechanism most relevant to that emotional state."
        )
        st.info(
            "**Data coverage note:** USDA micronutrient records are 30–60% complete. "
            "NULL values → 0 contribution (conservative rule). This avoids corpus collapse "
            "from hard DB filtering while still rewarding foods with documented nutrient data. "
            "A food with NULL for all zone-priority nutrients scores micro_score = 0 "
            "and ranks on macro + pref components only.",
            icon=":material/info:",
        )

        micro_rows = []
        for z in ["Q1_POS_ACT", "Q2_NEG_ACT", "Q3_NEG_DEACT", "NEUTRAL_BASELINE"]:
            z_priorities = ZONE_MICRONUTRIENT_PRIORITIES.get(z, [])
            rda_strs = []
            for col in z_priorities:
                label = NUTRIENT_DISPLAY_LABELS.get(col, col)
                rda   = RDA_REFERENCE.get(col)
                if rda:
                    unit = "µg" if col.endswith("_mcg") else ("g" if col.endswith("_g") else "mg")
                    rda_strs.append(f"{label} ({rda['male']}{unit}/day)")
                else:
                    rda_strs.append(label)
            micro_rows.append((ZONE_LABELS[z], len(z_priorities), ", ".join(rda_strs) or "—"))
        df_m = pd.DataFrame(
            micro_rows,
            columns=["Zone", "|N_Z|", "Priority Micronutrients (RDA/day, male)"],
        )
        st.dataframe(df_m, hide_index=True, use_container_width=True)

        st.markdown(
            "**Scientific example (Q3\_NEG\_DEACT):** "
            "A food with B12=2.1 µg, Vit D=8.5 µg, Folate=80 µg, Omega-3=900 mg "
            "scored for a male (meal fraction=0.35):\n\n"
            "- Folate: 80 / (400×0.35) = 0.571\n"
            "- B12: 2.1 / (2.4×0.35) = 2.5 → capped at **1.0**\n"
            "- Vit D: 8.5 / (15×0.35) = 1.62 → capped at **1.0**\n"
            "- Omega-3: 900 / (1600×0.35) = 1.61 → capped at **1.0**\n\n"
            "micro_score = (0.571 + 1.0 + 1.0 + 1.0) / 4 = **0.893**"
        )
        st.caption(
            "RDA values: NIH ODS Dietary Reference Intakes 2020. "
            "Fiber AI: male 38 g/day, female 25 g/day. "
            "Omega-3 AI: male 1600 mg/day, female 1100 mg/day. "
            "Zone priorities: Boyle et al. (2017) — Mg+B6+C/stress; "
            "Kennedy (2016) — B vitamins/fatigue; Jacka et al. (2017) — diet/depression; "
            "Cryan et al. (2019) — fiber/gut-brain axis; "
            "Gómez-Pinilla (2008) — brain foods."
        )

    # ── Appendix — Meal Database ──────────────────────────────────────────────
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

    # ── Full Reference List ───────────────────────────────────────────────────
    with st.expander("Full Reference List", expanded=False):
        refs = [
            "Ma, Z., et al. (2024). emotion2vec: Self-Supervised Pre-Training for Speech Emotion Representation. *Findings of ACL 2024*, 15747–15760. DOI: 10.18653/v1/2024.findings-acl.931",
            "Russell, J. A. (1980). A circumplex model of affect. *Journal of Personality and Social Psychology*, 39(6), 1161–1178. DOI: 10.1037/h0077714",
            "Posner, J., Russell, J. A., & Peterson, B. S. (2005). The circumplex model of affect. *Development and Psychopathology*, 17(3), 715–734. DOI: 10.1017/S0954579405050340",
            "Livingstone, S. R., & Russo, F. A. (2018). The Ryerson Audio-Visual Database of Emotional Speech and Song (RAVDESS). *PLOS ONE*, 13(5), e0196391. DOI: 10.1371/journal.pone.0196391",
            "Mifflin, M. D., et al. (1990). A new predictive equation for resting energy expenditure. *American Journal of Clinical Nutrition*, 51(2), 241–247. PMID: 2305711",
            "USDA (2020). *Dietary Guidelines for Americans 2020–2025*, 9th Edition.",
            "Wurtman, R. J., & Wurtman, J. J. (1995). Brain serotonin, carbohydrate-craving, obesity and depression. *Obesity Research*, 3(S4), 477S–480S. DOI: 10.1002/j.1550-8528.1995.tb00215.x",
            "Gómez-Pinilla, F. (2008). Brain foods: the effects of nutrients on brain function. *Nature Reviews Neuroscience*, 9(7), 568–578. DOI: 10.1038/nrn2421",
            "Jacka, F. N., et al. (2017). A randomised controlled trial of dietary improvement for adults with major depression (the SMILES trial). *BMC Medicine*, 15(1), 23. DOI: 10.1186/s12916-017-0791-y",
            "Boyle, N. B., Lawton, C., & Dye, L. (2017). The effects of magnesium supplementation on subjective anxiety and stress. *Nutrients*, 9(5), 429. DOI: 10.3390/nu9050429",
            "Kennedy, D. O. (2016). B vitamins and the brain: mechanisms, dose and efficacy. *Nutrients*, 8(2), 68. DOI: 10.3390/nu8020068",
            "Benton, D. (2002). Carbohydrate ingestion, blood glucose and mood. *Neuroscience & Biobehavioral Reviews*, 26(3), 293–308. DOI: 10.1016/S0149-7634(02)00003-6",
            "Cryan, J. F., et al. (2019). The microbiota-gut-brain axis. *Physiological Reviews*, 99(4), 1877–2013. DOI: 10.1152/physrev.00018.2018",
            "Macht, M. (2008). How emotions affect eating: a five-way model. *Appetite*, 50(1), 1–11. DOI: 10.1016/j.appet.2007.07.002",
            "NIH Office of Dietary Supplements (2020). *Dietary Reference Intakes (DRI) tables*. National Institutes of Health. URL: ods.od.nih.gov",
        ]
        for i, ref in enumerate(refs, 1):
            st.markdown(f"{i}. {ref}")


def _zone_mechanism(zone: str) -> str:
    """Short mechanism string for the NNV table."""
    return {
        "Q1_POS_ACT":       "Macht 2008 (emotion-eating risk)",
        "Q2_NEG_ACT":       "Wurtman 1995; Gómez-Pinilla 2008",
        "Q3_NEG_DEACT":     "Benton 2002; Gómez-Pinilla 2008",
        "NEUTRAL_BASELINE": "Jacka 2017 SMILES (Mediterranean)",
    }.get(zone, "")


show()
