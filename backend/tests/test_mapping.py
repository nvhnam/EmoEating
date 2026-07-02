import pytest
from emoeating.affect.mapping import DominantClassStrategy, to_valence_arousal
from emoeating import config


def test_dominant_class_picks_argmax():
    probs = {"happy": 0.6, "sad": 0.3, "neutral": 0.1}
    v, a = to_valence_arousal(probs)
    assert (v, a) == config.EMOTION_VA["happy"]


def test_dominant_class_strategy_directly():
    probs = {"angry": 0.7, "happy": 0.3}
    assert DominantClassStrategy().to_va(probs) == config.EMOTION_VA["angry"]


def test_empty_probs_raises():
    with pytest.raises(ValueError):
        to_valence_arousal({})


def test_unknown_label_raises():
    with pytest.raises(KeyError):
        to_valence_arousal({"ecstatic": 1.0})
