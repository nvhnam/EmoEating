import importlib.util

import numpy as np
import pytest

from emoeating import config
from emoeating.ser.encoder import Encoder, MockEncoder, Emotion2VecEncoder


def _wave():
    return np.zeros(16000 * 4, dtype=np.float32)


def test_mock_encoder_is_an_encoder():
    assert isinstance(MockEncoder(), Encoder)


def test_mock_default_output_is_canonical_and_normalized():
    probs = MockEncoder().predict(_wave())
    assert set(probs) == set(config.EMOTION_VA)
    assert sum(probs.values()) == pytest.approx(1.0)
    assert all(v >= 0.0 for v in probs.values())


def test_mock_parametrized_distribution():
    probs = MockEncoder({"angry": 3.0, "happy": 1.0}).predict(_wave())
    assert probs["angry"] == pytest.approx(0.75)
    assert probs["happy"] == pytest.approx(0.25)
    assert set(probs) == set(config.EMOTION_VA)


def test_mock_accepts_raw_labels_and_folds_unknown():
    probs = MockEncoder({"<unk>": 1.0, "happy": 1.0}).predict(_wave())
    assert probs["unknown"] == pytest.approx(0.5)
    assert probs["happy"] == pytest.approx(0.5)


_FUNASR_AVAILABLE = importlib.util.find_spec("funasr") is not None


def test_emotion2vec_encoder_is_an_encoder_without_loading():
    # Construction must NOT import funasr or download weights.
    enc = Emotion2VecEncoder()
    assert isinstance(enc, Encoder)
    assert enc._model is None  # not loaded yet


@pytest.mark.slow
@pytest.mark.skipif(not _FUNASR_AVAILABLE, reason="funasr/model not installed")
def test_emotion2vec_real_inference_on_short_clip():
    # 4s synthesized clip is enough to exercise the load + generate path.
    t = np.linspace(0.0, 4.0, 16000 * 4, endpoint=False)
    wave = (0.2 * np.sin(2 * np.pi * 180.0 * t)).astype(np.float32)

    probs = Emotion2VecEncoder().predict(wave)
    assert set(probs) == set(config.EMOTION_VA)
    assert sum(probs.values()) == pytest.approx(1.0, abs=1e-5)
    assert all(0.0 <= v <= 1.0 for v in probs.values())
