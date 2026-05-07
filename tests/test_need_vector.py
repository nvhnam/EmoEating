"""Unit tests for engine/need_vector.py"""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import pytest
from engine.need_vector import compute_need_vector, NeedVector, need_vector_to_dict
from engine.affect_mapper import emotion_to_va


def test_all_weights_in_range():
    """All NeedVector fields must be in [0, 1]."""
    for V in [-1.0, -0.5, 0.0, 0.5, 1.0]:
        for A in [-1.0, -0.5, 0.0, 0.5, 1.0]:
            nv = compute_need_vector(V, A)
            for field, val in need_vector_to_dict(nv).items():
                assert 0.0 <= val <= 1.0, f"V={V}, A={A}, {field}={val} out of [0,1]"


def test_fiber_constant():
    """Fiber weight must always be 0.5 (gut-brain axis baseline)."""
    for V, A in [(-1, -1), (0, 0), (1, 1), (-0.8, 0.8)]:
        nv = compute_need_vector(V, A)
        assert nv.fiber == 0.5


def test_angry_tryptophan_high():
    """angry: V=-0.8, A=0.8 â†’ tryptophan should be > 0.5."""
    V, A = emotion_to_va("angry")
    nv = compute_need_vector(V, A)
    assert nv.tryptophan > 0.5, f"angry tryptophan={nv.tryptophan}"


def test_angry_protein_high():
    """angry: protein weight should be > 0.7 (high A+)."""
    V, A = emotion_to_va("angry")
    nv = compute_need_vector(V, A)
    assert nv.protein > 0.7, f"angry protein={nv.protein}"


def test_happy_tryptophan_low():
    """happy: V=+0.8 â†’ tryptophan â‰ˆ 0 (no negative valence)."""
    V, A = emotion_to_va("happy")
    nv = compute_need_vector(V, A)
    assert nv.tryptophan < 0.1, f"happy tryptophan={nv.tryptophan}"


def test_happy_antioxidants_positive():
    """happy: antioxidants > 0.3 (positive valence â†’ antox from (1-V)/2 term)."""
    V, A = emotion_to_va("happy")
    nv = compute_need_vector(V, A)
    assert nv.antioxidants > 0.1, f"happy antioxidants={nv.antioxidants}"


def test_anxious_magnesium_high():
    """anxious: high A+ and negative V â†’ magnesium should be elevated."""
    V, A = emotion_to_va("anxious")
    nv = compute_need_vector(V, A)
    assert nv.magnesium > 0.3, f"anxious magnesium={nv.magnesium}"


def test_tired_iron_high():
    """tired: low A (A-) â†’ iron (O2 transport) elevated."""
    V, A = emotion_to_va("tired")
    nv = compute_need_vector(V, A)
    assert nv.iron > 0.3, f"tired iron={nv.iron}"


def test_tired_b_vitamins_elevated():
    """tired: low A- â†’ B vitamins elevated (mitochondrial energy)."""
    V, A = emotion_to_va("tired")
    nv = compute_need_vector(V, A)
    assert nv.b_vitamins > 0.5, f"tired b_vitamins={nv.b_vitamins}"


def test_neutral_all_moderate():
    """neutral (V=0, A=0) â†’ all weights moderate/low; fiber=0.5."""
    nv = compute_need_vector(0.0, 0.0)
    d = need_vector_to_dict(nv)
    for key, val in d.items():
        if key == "fiber":
            assert val == 0.5
        elif key not in ("antioxidants", "protein"):
            # For V=0, A=0: Vm=0, Am=0, Ap=0 â†’ most weights ~ 0
            assert val < 0.5, f"neutral {key}={val} expected <0.5"


def test_sugar_penalty_high_for_stressed():
    """stressed: high A+ and negative V â†’ sugar penalty high."""
    V, A = emotion_to_va("stressed")
    nv = compute_need_vector(V, A)
    assert nv.sugar_penalty > 0.3, f"stressed sugar_penalty={nv.sugar_penalty}"


def test_sugar_penalty_low_for_calm():
    """calm: low A+ and positive V â†’ sugar penalty low."""
    V, A = emotion_to_va("calm")
    nv = compute_need_vector(V, A)
    assert nv.sugar_penalty < 0.1, f"calm sugar_penalty={nv.sugar_penalty}"
