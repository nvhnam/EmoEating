import pytest

from emoeating import config
from emoeating.ser import labels


def test_canonical_labels_match_config_exactly():
    assert set(labels.CANONICAL_LABELS) == set(config.EMOTION_VA)
    assert len(labels.CANONICAL_LABELS) == 9


def test_direct_label_passthrough():
    assert labels.canonical_for("angry") == "angry"
    assert labels.canonical_for("Happy") == "happy"
    assert labels.canonical_for("  neutral ") == "neutral"


def test_unk_token_folds_to_unknown():
    assert labels.canonical_for("<unk>") == "unknown"
    assert labels.canonical_for("unk") == "unknown"
    assert labels.canonical_for("totally_made_up") == "unknown"


def test_chinese_gloss_form_resolves():
    # FunASR sometimes emits "gloss/english" or "english/gloss"
    assert labels.canonical_for("生气/angry") == "angry"
    assert labels.canonical_for("angry/愤怒") == "angry"


def test_normalize_returns_all_nine_keys_and_sums_to_one():
    raw = {"angry": 0.5, "happy": 0.3, "neutral": 0.2}
    probs = labels.normalize_emotion_scores(raw)
    assert set(probs) == set(config.EMOTION_VA)
    assert sum(probs.values()) == pytest.approx(1.0)
    assert probs["angry"] == pytest.approx(0.5)


def test_unknown_mass_is_summed():
    raw = {"<unk>": 0.4, "totally_made_up": 0.1, "happy": 0.5}
    probs = labels.normalize_emotion_scores(raw)
    assert probs["unknown"] == pytest.approx(0.5)
    assert probs["happy"] == pytest.approx(0.5)


def test_zero_mass_defaults_to_unknown():
    probs = labels.normalize_emotion_scores({})
    assert probs["unknown"] == pytest.approx(1.0)
    assert sum(probs.values()) == pytest.approx(1.0)


def test_negative_mass_returns_canonical_unknown_distribution():
    # All-negative input must still produce a valid canonical distribution.
    probs = labels.normalize_emotion_scores({"happy": -1.0})
    assert set(probs) == set(config.EMOTION_VA)
    assert sum(probs.values()) == pytest.approx(1.0)
    assert probs["unknown"] == pytest.approx(1.0)
