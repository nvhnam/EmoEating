"""
Computes the nutritional need weight vector N(V, A) from affective coordinates.
All weights âˆˆ [0, 1]. Research citations embedded as comments.

References:
  Wurtman & Wurtman (1995) â€” tryptophan, carbohydrate-serotonin link
  Grosso et al. (2014) â€” omega-3 and depression
  Boyle et al. (2017) â€” magnesium and anxiety
  Kennedy (2016) â€” B vitamins and brain function
  Lopresti (2020) â€” B vitamins and mitochondrial energy
  Bouayed et al. (2009) â€” antioxidants and emotional stress
  Young (2007) â€” tyrosine, dopamine, protein
  Cryan et al. (2019) â€” gut-brain axis, fiber
  Gangwisch et al. (2015) â€” glycemic index and depression
"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import dataclass


@dataclass
class NeedVector:
    tryptophan: float    # w_trp  â€” serotonin precursor (Wurtman & Wurtman 1995)
    omega3: float        # w_om3  â€” anti-depressant (Grosso et al. 2014)
    complex_carbs: float # w_carb â€” serotonin / energy (Wurtman 1995; Gangwisch 2015)
    magnesium: float     # w_mag  â€” HPA axis / anxiety (Boyle et al. 2017)
    iron: float          # w_fe   â€” O2 transport / fatigue (Kennedy 2016)
    b_vitamins: float    # w_bvit â€” brain energy (Kennedy 2016; Lopresti 2020)
    antioxidants: float  # w_antx â€” oxidative stress (Bouayed et al. 2009)
    protein: float       # w_prot â€” dopamine precursor (Young 2007)
    fiber: float         # w_fib  â€” gut-brain axis baseline (Cryan et al. 2019)
    sugar_penalty: float # p_sug  â€” GI spike penalty (Gangwisch et al. 2015)


def compute_need_vector(V: float, A: float) -> NeedVector:
    """
    N(V, A) â†’ NeedVector

    Let:
        Vâ» = max(0, âˆ’V)   # negative valence magnitude
        Aâ» = max(0, âˆ’A)   # low arousal magnitude
        Aâº = max(0,  A)   # high arousal magnitude

    Formula (all weights clipped to [0,1]):
        w_trp  = min(1, 1.5 Â· Vâ»)
        w_om3  = min(1, 1.2 Â· Vâ» Â· (1 âˆ’ 0.4 Â· Aâº))
        w_carb = min(1, 0.8 Â· Vâ» + 0.4 Â· Aâ»)
        w_mag  = min(1, 1.4 Â· Aâº Â· Vâ» + 0.3 Â· Vâ»)
        w_fe   = min(1, 1.3 Â· Aâ» + 0.2 Â· Vâ»)
        w_bvit = min(1, 1.2 Â· Aâ» + 0.3 Â· Vâ»)
        w_antx = min(1, 0.7 Â· (1 âˆ’ V) / 2 + 0.3 Â· Aâº)
        w_prot = min(1, 0.4 + 0.4 Â· Aâº)
        w_fib  = 0.5   (constant â€” gut-brain axis baseline)
        p_sug  = min(1, 0.8 Â· Aâº Â· Vâ» + 0.3 Â· Aâº)
    """
    Vm = max(0.0, -V)   # Vâ»
    Am = max(0.0, -A)   # Aâ»
    Ap = max(0.0,  A)   # Aâº

    w_trp  = min(1.0, 1.5 * Vm)
    w_om3  = min(1.0, 1.2 * Vm * (1.0 - 0.4 * Ap))
    w_carb = min(1.0, 0.8 * Vm + 0.4 * Am)
    w_mag  = min(1.0, 1.4 * Ap * Vm + 0.3 * Vm)
    w_fe   = min(1.0, 1.3 * Am + 0.2 * Vm)
    w_bvit = min(1.0, 1.2 * Am + 0.3 * Vm)
    w_antx = min(1.0, 0.7 * (1.0 - V) / 2.0 + 0.3 * Ap)
    w_prot = min(1.0, 0.4 + 0.4 * Ap)
    w_fib  = 0.5
    p_sug  = min(1.0, 0.8 * Ap * Vm + 0.3 * Ap)

    return NeedVector(
        tryptophan=w_trp,
        omega3=w_om3,
        complex_carbs=w_carb,
        magnesium=w_mag,
        iron=w_fe,
        b_vitamins=w_bvit,
        antioxidants=w_antx,
        protein=w_prot,
        fiber=w_fib,
        sugar_penalty=p_sug,
    )


def need_vector_from_emotion(emotion_label: str) -> NeedVector:
    """Convenience wrapper: emotion string â†’ NeedVector."""
    from engine.affect_mapper import emotion_to_va
    V, A = emotion_to_va(emotion_label)
    return compute_need_vector(V, A)


def need_vector_to_dict(nv: NeedVector) -> dict:
    """Serialize NeedVector to dict for display/logging."""
    return {
        "tryptophan":    nv.tryptophan,
        "omega3":        nv.omega3,
        "complex_carbs": nv.complex_carbs,
        "magnesium":     nv.magnesium,
        "iron":          nv.iron,
        "b_vitamins":    nv.b_vitamins,
        "antioxidants":  nv.antioxidants,
        "protein":       nv.protein,
        "fiber":         nv.fiber,
        "sugar_penalty": nv.sugar_penalty,
    }
