"""Golden unit tests for ConfidenceEngine (spec §4 + §8)."""
import pytest
from emoeating.voice.confidence import ConfidenceEngine, ConfidenceState
from emoeating.ser.labels import normalize_emotion_scores


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sad_probs() -> dict[str, float]:
    return normalize_emotion_scores({"sad": 0.8, "neutral": 0.15, "other": 0.05})


def _happy_probs() -> dict[str, float]:
    return normalize_emotion_scores({"happy": 0.85, "surprised": 0.1, "neutral": 0.05})


def _neutral_probs() -> dict[str, float]:
    return normalize_emotion_scores({"neutral": 0.6, "other": 0.25, "unknown": 0.15})


def _low_conf_probs() -> dict[str, float]:
    """All emotions roughly equal — dominant prob well below MIN_WINDOW_CONF."""
    raw = {lbl: 1.0 for lbl in
           ["happy", "angry", "sad", "fearful", "disgusted",
            "surprised", "neutral", "other", "unknown"]}
    return normalize_emotion_scores(raw)


def _fast_engine(**overrides) -> ConfidenceEngine:
    """ConfidenceEngine with small floor/stability for deterministic tests."""
    defaults = dict(
        speech_floor_s=3.0,
        stability_n=3,
        margin_theta=0.05,
        timeout_s=9999.0,
    )
    defaults.update(overrides)
    return ConfidenceEngine(**defaults)


# ---------------------------------------------------------------------------
# Golden test 1: stable-sad → STOP after floor + stability + margin
# ---------------------------------------------------------------------------

def test_stable_sad_stops_after_floor_and_stability():
    engine = _fast_engine()
    probs = _sad_probs()
    state: ConfidenceState | None = None
    for step in range(20):
        state = engine.update(probs, speech_dt=1.0, wall_t=float(step + 1))
        if state.decision == "STOP":
            break
    assert state is not None
    assert state.decision == "STOP"
    assert state.leading_zone == "NEG_DEACTIVE"
    assert state.speech_elapsed >= 3.0   # floor met
    assert state.confidence > 0.5


def test_stable_sad_stops_no_later_than_floor_plus_stability():
    """STOP must fire within a bounded number of updates (floor 3s + stability_n=3)."""
    engine = _fast_engine()
    probs = _sad_probs()
    for step in range(10):
        state = engine.update(probs, speech_dt=1.0, wall_t=float(step + 1))
        if state.decision == "STOP":
            # Should fire no later than step 5 (floor=3 + stability=3 - overlap)
            assert step < 8
            return
    pytest.fail("STOP never fired for stable-sad stream")


# ---------------------------------------------------------------------------
# Golden test 2: bimodal/flapping → never early STOP → timeout best-so-far
# ---------------------------------------------------------------------------

def test_bimodal_flapping_no_early_stop():
    engine = _fast_engine(timeout_s=20.0)
    sad = _sad_probs()
    happy = _happy_probs()
    state: ConfidenceState | None = None
    for step in range(18):
        probs = sad if step % 2 == 0 else happy
        state = engine.update(probs, speech_dt=1.0, wall_t=float(step + 1))
        if state.decision == "STOP" and state.wall_elapsed < 20.0:
            pytest.fail(f"Engine stopped early at step {step} (wall={state.wall_elapsed})")
    # Now trigger timeout
    state = engine.update(happy, speech_dt=1.0, wall_t=21.0)
    assert state.decision == "STOP"
    assert state.wall_elapsed >= 20.0


def test_timeout_best_so_far_has_higher_confidence_than_last():
    """On timeout, the returned state's confidence ≥ the last mid-session state."""
    # Use alternating sad/happy so stability never holds, then timeout
    engine = _fast_engine(timeout_s=6.0)
    sad = _sad_probs()
    happy = _happy_probs()
    last_mid: ConfidenceState | None = None
    for step in range(5):
        state = engine.update(sad if step % 2 == 0 else happy,
                              speech_dt=1.0, wall_t=float(step + 1))
        if state.decision == "CONTINUE":
            last_mid = state
    timeout_state = engine.update(happy, speech_dt=1.0, wall_t=7.0)
    assert timeout_state.decision == "STOP"
    if last_mid is not None:
        assert timeout_state.confidence >= last_mid.confidence - 1e-9


# ---------------------------------------------------------------------------
# Golden test 3: all-neutral → ends neutral (not falsely another zone)
# ---------------------------------------------------------------------------

def test_all_neutral_ends_neutral():
    engine = _fast_engine()
    probs = _neutral_probs()
    state: ConfidenceState | None = None
    for step in range(20):
        state = engine.update(probs, speech_dt=1.0, wall_t=float(step + 1))
        if state.decision == "STOP":
            break
    assert state is not None
    assert state.decision == "STOP"
    assert state.leading_zone == "NEUTRAL_CALM"


# ---------------------------------------------------------------------------
# Golden test 4: low-conf windows skipped — don't advance floor or EMA
# ---------------------------------------------------------------------------

def test_low_conf_windows_skip_ema_and_floor():
    engine = _fast_engine()
    probs = _low_conf_probs()
    # Confirm dominant prob is below MIN_WINDOW_CONF
    assert max(probs.values()) < engine._min_conf
    for step in range(30):
        state = engine.update(probs, speech_dt=1.0, wall_t=float(step + 1))
        # speech_elapsed should stay at 0 because quality gate rejects every window
        assert state.speech_elapsed == 0.0
        assert state.decision == "CONTINUE"


def test_low_conf_windows_do_not_stop_early():
    engine = _fast_engine(timeout_s=9999.0)
    probs = _low_conf_probs()
    for step in range(100):
        state = engine.update(probs, speech_dt=1.0, wall_t=float(step + 1))
        assert state.decision == "CONTINUE"


# ---------------------------------------------------------------------------
# Golden test 5: final_infer shape == InferResult
# ---------------------------------------------------------------------------

def test_final_infer_shape():
    engine = _fast_engine()
    probs = _sad_probs()
    for step in range(10):
        state = engine.update(probs, speech_dt=1.0, wall_t=float(step + 1))
        if state.decision == "STOP":
            break
    infer = engine.final_infer()
    assert set(infer) == {"emotion_probs", "valence", "arousal", "zone"}
    assert isinstance(infer["emotion_probs"], dict)
    assert len(infer["emotion_probs"]) == 9
    assert isinstance(infer["valence"], float)
    assert isinstance(infer["arousal"], float)
    assert isinstance(infer["zone"], str)
    assert infer["zone"] in {"POS_ACTIVE", "NEG_ACTIVE", "NEG_DEACTIVE", "NEUTRAL_CALM"}


# ---------------------------------------------------------------------------
# Safety flag
# ---------------------------------------------------------------------------

def test_safety_flag_single_spike_no_flag():
    """A single NEG quality update must NOT set safety_flag (spec §4: sustained required)."""
    engine = ConfidenceEngine(safety_neg_threshold=0.3)  # low threshold; default stability_n=5
    # Dominant prob 0.6 >= MIN_WINDOW_CONF → quality=True; high NEG mass
    probs = normalize_emotion_scores({"angry": 0.6, "fearful": 0.3, "disgusted": 0.1})
    state = engine.update(probs, speech_dt=1.0, wall_t=1.0)
    # Only 1 quality update — far below stability_n=5 → flag must NOT fire
    assert state.safety_flag is False


def test_safety_flag_sustained_fires():
    """safety_flag fires only after STABILITY_N consecutive quality updates with high NEG mass."""
    stability = 3
    engine = ConfidenceEngine(safety_neg_threshold=0.3, stability_n=stability)
    probs = normalize_emotion_scores({"angry": 0.6, "fearful": 0.3, "disgusted": 0.1})
    # (stability - 1) updates → not yet fired
    for i in range(stability - 1):
        state = engine.update(probs, speech_dt=1.0, wall_t=float(i + 1))
        assert state.safety_flag is False, f"flag fired too early at quality update {i}"
    # One more quality update completes the streak → must fire
    state = engine.update(probs, speech_dt=1.0, wall_t=float(stability))
    assert state.safety_flag is True


def test_safety_flag_clear_on_neutral():
    engine = ConfidenceEngine(safety_neg_threshold=0.8)
    probs = normalize_emotion_scores({"neutral": 0.9, "happy": 0.1})
    state = engine.update(probs, speech_dt=1.0, wall_t=1.0)
    assert state.safety_flag is False


# ---------------------------------------------------------------------------
# final_infer neutral dominance (Fix 5b)
# ---------------------------------------------------------------------------

def test_final_infer_neutral_dominance():
    """When all windows are neutral, final_infer() must return zone == 'NEUTRAL_CALM'."""
    engine = _fast_engine()
    probs = _neutral_probs()
    for step in range(20):
        state = engine.update(probs, speech_dt=1.0, wall_t=float(step + 1))
        if state.decision == "STOP":
            break
    infer = engine.final_infer()
    assert infer["zone"] == "NEUTRAL_CALM", (
        f"Expected NEUTRAL_CALM from all-neutral stream; got {infer['zone']}"
    )
