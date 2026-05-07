"""
Page 5 — Methodology (research transparency).
Displays the full formula pipeline with citations and a live demo.
"""

from __future__ import annotations

import streamlit as st
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import EMOTION_COORDS


def show():
    st.title("Methodology")
    st.markdown(
        "This page documents the computational pipeline underpinning MoodMeal's "
        "recommendations. It is included for research transparency and reviewer access."
    )

    # ── 1. Emotion Detection ─────────────────────────────────────────────────
    with st.expander("1. Emotion Detection", expanded=True):
        st.markdown(
            "Voice-based emotion detection is pending integration. The system currently "
            "accepts a user-selected emotion label from 11 predefined classes based on "
            "the Ekman (1992) taxonomy of acute, event-triggered emotions."
        )
        st.caption(
            "Ekman, P. (1992). An argument for basic emotions. "
            "_Cognition & Emotion_, 6(3–4), 169–200."
        )

    # ── 2. Dimensional Affect Mapping ────────────────────────────────────────
    with st.expander("2. Dimensional Affect Mapping — Russell Circumplex", expanded=True):
        st.markdown(
            "Each emotion label is mapped to a (Valence, Arousal) coordinate pair "
            "using the Russell Circumplex Model of Affect (1980)."
        )
        st.latex(r"\text{emotion} \xrightarrow{\text{Table 1}} (V, A) \in [-1, 1]^2")

        rows = [(e, m["V"], m["A"], m["emoji"]) for e, m in EMOTION_COORDS.items()]
        import pandas as pd
        df = pd.DataFrame(rows, columns=["Emotion", "Valence (V)", "Arousal (A)", "Emoji"])
        st.dataframe(df, hide_index=True, use_container_width=True)

        st.caption(
            "Russell, J. A. (1980). A circumplex model of affect. "
            "_Journal of Personality and Social Psychology_, 39(6), 1161–1178.\n\n"
            "Posner, J., Russell, J. A., & Peterson, B. S. (2005). "
            "_Development and Psychopathology_, 17(3), 715–734."
        )

    # ── 3. Nutritional Need Vector N(V,A) ────────────────────────────────────
    with st.expander("3. Nutritional Need Vector N(V, A)", expanded=True):
        st.markdown(
            r"""
            Given $V^- = \max(0, -V)$, $A^- = \max(0, -A)$, $A^+ = \max(0, A)$:
            """
        )
        st.latex(r"""
\begin{aligned}
w_{trp}  &= \min(1,\ 1.5 \cdot V^-)  &&\text{(tryptophan → serotonin)} \\
w_{om3}  &= \min(1,\ 1.2 \cdot V^- \cdot (1 - 0.4 \cdot A^+))  &&\text{(omega-3 → mood)} \\
w_{carb} &= \min(1,\ 0.8 \cdot V^- + 0.4 \cdot A^-)  &&\text{(complex carbs → energy)} \\
w_{mag}  &= \min(1,\ 1.4 \cdot A^+ \cdot V^- + 0.3 \cdot V^-)  &&\text{(Mg → HPA axis)} \\
w_{fe}   &= \min(1,\ 1.3 \cdot A^- + 0.2 \cdot V^-)  &&\text{(iron → O}_2\text{ transport)} \\
w_{bvit} &= \min(1,\ 1.2 \cdot A^- + 0.3 \cdot V^-)  &&\text{(B vitamins → mitochondria)} \\
w_{antx} &= \min(1,\ 0.7 \cdot \tfrac{1-V}{2} + 0.3 \cdot A^+)  &&\text{(antioxidants → stress)} \\
w_{prot} &= \min(1,\ 0.4 + 0.4 \cdot A^+)  &&\text{(protein → dopamine)} \\
w_{fib}  &= 0.5  &&\text{(fiber — gut-brain axis constant)} \\
p_{sug}  &= \min(1,\ 0.8 \cdot A^+ \cdot V^- + 0.3 \cdot A^+)  &&\text{(sugar penalty)}
\end{aligned}
""")

        st.markdown("**Live demo:**")
        demo_emo = st.selectbox("Select emotion", list(EMOTION_COORDS.keys()), key="method_demo_emo")
        if demo_emo:
            from engine.affect_mapper import emotion_to_va
            from engine.need_vector import compute_need_vector, need_vector_to_dict
            V, A = emotion_to_va(demo_emo)
            nv = compute_need_vector(V, A)
            nvd = need_vector_to_dict(nv)
            from components.nutrient_bars import render_nutrient_bars
            render_nutrient_bars(nv)

        st.caption(
            "Key references: Wurtman & Wurtman (1995); Grosso et al. (2014); "
            "Boyle et al. (2017); Kennedy (2016); Lopresti (2020); "
            "Bouayed et al. (2009); Young (2007); Cryan et al. (2019); Gangwisch et al. (2015)."
        )

    # ── 4. Food Scoring S(f) ─────────────────────────────────────────────────
    with st.expander("4. Food Scoring Function S(f)", expanded=False):
        st.markdown(
            "Each food's nutrient values are min-max normalised across the full corpus "
            r"using a pre-computed normalization cache: $\hat{n}_i(f) = (n_i - \min_j n_i(j)) / (\max_j n_i(j) - \min_j n_i(j) + \varepsilon)$"
        )
        st.latex(r"""
\begin{aligned}
\text{antox}(f) &= 0.6 \cdot \hat{n}_{vitC}(f) + 0.4 \cdot \hat{n}_{vitE}(f) \\
\text{bvit}(f)  &= \tfrac{\hat{n}_{B12}(f) + \hat{n}_{folate}(f)}{2} \\[6pt]
S(f) &= w_{trp} \cdot \hat{n}_{trp}
       + w_{om3} \cdot \hat{n}_{om3}
       + w_{carb} \cdot \hat{n}_{carb}
       + w_{mag} \cdot \hat{n}_{mag}
       + w_{fe} \cdot \hat{n}_{fe} \\
     &\quad + w_{bvit} \cdot \text{bvit}
       + w_{antx} \cdot \text{antox}
       + w_{prot} \cdot \hat{n}_{prot}
       + w_{fib} \cdot \hat{n}_{fib}
       - p_{sug} \cdot \hat{n}_{sug}
\end{aligned}
""")
        st.caption("NULL nutrient values are treated as 0 (conservative, not imputed).")

    # ── 5. Physiological Profile Adaptation ─────────────────────────────────
    with st.expander("5. Physiological Profile Adaptation", expanded=False):
        st.markdown("**Mifflin-St Jeor BMR equation (1990) — current clinical standard:**")
        st.latex(r"""
\text{BMR}_{\text{male}} = 10w + 6.25h - 5a + 5 \quad [\text{kcal/day}]
""")
        st.latex(r"""
\text{BMR}_{\text{female}} = 10w + 6.25h - 5a - 161 \quad [\text{kcal/day}]
""")
        st.latex(r"""
\text{TDEE} = \text{BMR} \times 1.2 \qquad \text{(sedentary, post-work scenario)}
""")
        st.latex(r"""
\text{Meal target} = \frac{\text{TDEE}}{3}
""")
        st.markdown("**Final score blend:**")
        st.latex(r"""
\text{Score}_{\text{final}}(f) = 0.7 \cdot S(f) + 0.3 \cdot \left(1 - \frac{|C_f - C^*|}{C^*}\right)
""")
        st.caption(
            r"$C_f$ = food calories, $C^*$ = per-meal caloric target. "
            "Weights AFFECTIVE_WEIGHT=0.7 and CALORIC_WEIGHT=0.3 are hyperparameters "
            "defined in config.py.\n\n"
            "Mifflin et al. (1990). _American Journal of Clinical Nutrition_, 51(2), 241–247.\n\n"
            "WHO (2000). Obesity: preventing and managing the global epidemic."
        )

    # ── 6. Database Corpus ───────────────────────────────────────────────────
    with st.expander("6. Meal Database", expanded=False):
        st.markdown(
            "The meal corpus is assembled from five publicly available datasets:\n\n"
            "| Source | Dataset | Size |\n"
            "|--------|---------|------|\n"
            "| Food.com | RAW_recipes | ~231,637 recipes |\n"
            "| USDA Nutritional DB | nutrition.csv | ~8,789 foods |\n"
            "| Open Food Facts | products.tsv | filtered subset |\n"
            "| Epicurious | epi_r.csv | ~20,000 recipes |\n"
            "| Indian Food | indian_food.csv | regional diversity |\n\n"
            "**Quality filters:** calories > 50 kcal, protein > 2g, "
            "data_completeness ≥ 5/13 mood-relevant nutrients, "
            "prep+cook time < 120 min."
        )
        try:
            from db.connection import test_connection
            from db.queries import get_corpus_stats
            if test_connection():
                stats = get_corpus_stats()
                import pandas as pd
                st.dataframe(pd.DataFrame(stats), hide_index=True, use_container_width=True)
        except Exception:
            st.caption("Database not connected — corpus statistics unavailable.")

    # ── 7. References ─────────────────────────────────────────────────────────
    with st.expander("7. Full Reference List", expanded=False):
        refs = [
            "Ekman, P. (1992). An argument for basic emotions. *Cognition & Emotion*, 6(3–4), 169–200.",
            "Russell, J. A. (1980). A circumplex model of affect. *Journal of Personality and Social Psychology*, 39(6), 1161–1178.",
            "Posner, J., Russell, J. A., & Peterson, B. S. (2005). The circumplex model of affect. *Development and Psychopathology*, 17(3), 715–734.",
            "Wurtman, R. J., & Wurtman, J. J. (1995). Brain serotonin, carbohydrate-craving, obesity and depression. *Obesity Research*, 3(S4), 477S–480S.",
            "Grosso, G. et al. (2014). Role of omega-3 fatty acids in the treatment of depressive disorders. *PLOS ONE*, 9(5).",
            "Boyle, N. B., Lawton, C., & Dye, L. (2017). The effects of magnesium supplementation on subjective anxiety and stress. *Nutrients*, 9(5), 429.",
            "Kennedy, D. O. (2016). B vitamins and the brain. *Nutrients*, 8(2), 68.",
            "Lopresti, A. L. (2020). The effects of psychological and environmental stress on micronutrient concentrations in the body. *Advances in Nutrition*, 11(1), 103–112.",
            "Bouayed, J., Rammal, H., & Soulimani, R. (2009). Oxidative stress and anxiety. *Oxidative Medicine and Cellular Longevity*, 2(2), 63–67.",
            "Young, S. N. (2007). How to increase serotonin in the human brain without drugs. *Journal of Psychiatry & Neuroscience*, 32(6), 394–399.",
            "Cryan, J. F., et al. (2019). The microbiota-gut-brain axis. *Physiological Reviews*, 99(4), 1877–2013.",
            "Gangwisch, J. E., et al. (2015). High glycemic index diet as a risk factor for depression. *American Journal of Clinical Nutrition*, 102(2), 454–463.",
            "Macht, M. (2008). How emotions affect eating. *Appetite*, 50(1), 1–11.",
            "WHO (2000). Obesity: preventing and managing the global epidemic. Report of a WHO Consultation.",
            "Mifflin, M. D., et al. (1990). A new predictive equation for resting energy expenditure. *American Journal of Clinical Nutrition*, 51(2), 241–247.",
        ]
        for i, ref in enumerate(refs, 1):
            st.markdown(f"{i}. {ref}")

show()
