"""
SER Backend B: emotion2vec_plus_large backbone + CREMA-D linear probe (4-class).

Replaces the 9-class classification head with nn.Linear(1024, 4) trained on CREMA-D.
4 classes: anger (neg-active), happy (pos-active), sad_fearful (neg-deactive), neutral.
Best seed val WA = 92.9 %, valence CCC = 0.83 (5-seed mean) on CREMA-D.

The backbone (emotion2vec_plus_large) is unchanged and shared with Backend A.
Embeddings are extracted with extract_embedding=True (1024-d utterance vector),
then passed through the linear probe with z-score normalisation baked into buffers.

Probe files: app/models/best_linear_probe.pt, app/models/linear_probe_config.json
"""

from __future__ import annotations

import json
import os
import tempfile
import logging

import numpy as np
import torch
import torch.nn as nn

logger = logging.getLogger(__name__)

BACKEND_ID    = "crema4class"
BACKEND_LABEL = "emotion2vec + CREMA-D probe (4-class)"
N_CLASSES     = 4

# CREMA probe's zone strings → system canonical zone names
# Note: this backend's 4 classes map 1:1 onto the 4 zones, so the zone-mass
# aggregation in predict_zone_from_audio() below is numerically identical to a
# plain argmax here. It's kept for consistency with the 9-class backend
# (_ser_original.py), where several classes share a zone and marginalising
# over the full distribution can change the outcome vs. per-class argmax.
_PROBE_ZONE_TO_SYSTEM: dict[int, tuple[str, str]] = {
    # label_id: (probe_zone_name, system_canonical_zone)
    0: ("neg_active",   "Q2_NEG_ACT"),       # anger/disgust
    1: ("pos_active",   "Q1_POS_ACT"),       # happy
    2: ("neg_deactive", "Q3_NEG_DEACT"),     # sad/fearful
    3: ("neutral",      "NEUTRAL_BASELINE"), # neutral
}

# Resolved at import time — engine/ is one level below app/
_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_backbone    = None   # FunASR AutoModel (same backbone as Backend A)
_probe       = None   # LinearProbeWithNorm
_label_names = None   # dict[str, str]  {"0": "anger", ...}
_probe_device = None


class _LinearProbeWithNorm(nn.Module):
    """nn.Linear(1024, 4) with z-score normalisation baked in as buffers."""
    def __init__(self, input_dim: int = 1024, n_classes: int = 4,
                 mu=None, std=None):
        super().__init__()
        self.fc = nn.Linear(input_dim, n_classes)
        if mu is not None and std is not None:
            self.register_buffer("mu",  torch.tensor(mu,  dtype=torch.float32))
            self.register_buffer("std", torch.tensor(std, dtype=torch.float32))
        else:
            self.register_buffer("mu",  torch.zeros(input_dim))
            self.register_buffer("std", torch.ones(input_dim))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc((x - self.mu) / self.std)


def _get_backbone():
    global _backbone
    if _backbone is not None:
        return _backbone
    try:
        from funasr import AutoModel  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "FunASR is not installed. Run:\n"
            "  pip install funasr modelscope\n"
            "then restart the application."
        ) from exc
    from config import SER_MODEL_ID
    logger.info("Loading emotion2vec_plus_large backbone (CREMA probe) — first call only...")
    _backbone = AutoModel(
        model=SER_MODEL_ID,
        trust_remote_code=True,
        disable_update=True,
    )
    logger.info("emotion2vec_plus_large backbone loaded.")
    return _backbone


def _get_probe():
    global _probe, _label_names, _probe_device
    if _probe is not None:
        return _probe, _label_names, _probe_device

    probe_path  = os.path.join(_APP_DIR, "models", "best_linear_probe.pt")
    config_path = os.path.join(_APP_DIR, "models", "linear_probe_config.json")

    if not os.path.isfile(probe_path):
        raise FileNotFoundError(
            f"CREMA probe not found at {probe_path}. "
            "Copy best_linear_probe.pt and linear_probe_config.json to app/models/."
        )

    with open(config_path, encoding="utf-8") as f:
        cfg = json.load(f)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    probe = _LinearProbeWithNorm(cfg["embedding_dim"], cfg["n_classes"])
    state = torch.load(probe_path, map_location=device, weights_only=True)
    probe.load_state_dict(state)
    probe.to(device)
    probe.eval()

    _probe        = probe
    _label_names  = cfg["label_names"]   # {"0": "anger", "1": "happy", ...}
    _probe_device = device
    logger.info("CREMA-D linear probe loaded (device=%s).", device)
    return _probe, _label_names, _probe_device


def predict_zone_from_audio(audio_bytes: bytes) -> tuple[str, dict[str, float]]:
    """16 kHz WAV bytes → (canonical zone, 4-class prob dict)."""
    backbone = _get_backbone()
    probe, label_names, device = _get_probe()

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
    try:
        with os.fdopen(tmp_fd, "wb") as f:
            f.write(audio_bytes)
        result = backbone.generate(
            input=tmp_path,
            granularity="utterance",
            extract_embedding=True,
        )
    except Exception as exc:
        raise RuntimeError(f"SER (CREMA probe) inference failed: {exc}") from exc
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    feat = result[0]["feats"]
    if len(feat.shape) > 1:
        feat = feat.mean(axis=0)

    expected_dim = probe.fc.in_features
    if feat.shape[-1] != expected_dim:
        from config import SER_MODEL_ID
        raise RuntimeError(
            f"CREMA-D probe expects {expected_dim}-d embeddings but the active "
            f"backbone ({SER_MODEL_ID}) produced {feat.shape[-1]}-d ones. "
            "app/models/best_linear_probe.pt was trained specifically on "
            "emotion2vec_plus_large embeddings and is NOT compatible with a "
            "different-sized backbone — retrain the probe before using "
            "'crema4class' with this SER_MODEL_ID, or switch SER_BACKEND to "
            "'original' in config.py (works with any backbone size)."
        )

    feat_t = torch.tensor(feat.astype(np.float32),
                          dtype=torch.float32).unsqueeze(0).to(device)

    with torch.no_grad():
        logits    = probe(feat_t)
        probs_arr = torch.softmax(logits, dim=-1).cpu().numpy()[0]

    zone_mass: dict[str, float] = dict.fromkeys(
        {sys_zone for _, sys_zone in _PROBE_ZONE_TO_SYSTEM.values()}, 0.0
    )
    for i in range(N_CLASSES):
        _, sys_zone = _PROBE_ZONE_TO_SYSTEM[i]
        zone_mass[sys_zone] += float(probs_arr[i])
    system_zone = max(zone_mass, key=zone_mass.get)
    probs = {label_names[str(i)]: float(probs_arr[i]) for i in range(N_CLASSES)}
    return system_zone, probs


def is_available() -> bool:
    try:
        import funasr  # noqa: F401
        import torch   # noqa: F401
        probe_path = os.path.join(_APP_DIR, "models", "best_linear_probe.pt")
        return os.path.isfile(probe_path)
    except ImportError:
        return False
