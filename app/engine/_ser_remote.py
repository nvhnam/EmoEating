"""
SER Backend (client-side proxy): forwards audio to a remote inference server.

Used instead of importing funasr/modelscope/torch in-process when
SER_REMOTE_URL is configured — Streamlit Community Cloud's free-tier RAM
budget cannot load emotion2vec_plus_large, so the app calls out to an
identical copy of engine/ser_engine.py running as a FastAPI service
elsewhere (see server/main.py) instead. The server executes the exact same
_ser_crema.py / _ser_original.py code, so results are produced by the
identical model regardless of where the app is deployed — only the compute
location changes, not the measurement instrument.

This module has no heavy dependencies (requests only), so importing it never
pulls in torch — safe to import on a lean cloud install.
"""

from __future__ import annotations

import logging

import requests

from config import SER_REMOTE_TIMEOUT_S, SER_REMOTE_TOKEN, SER_REMOTE_URL

logger = logging.getLogger(__name__)


def _base_url() -> str:
    return SER_REMOTE_URL.rstrip("/")


def _headers() -> dict:
    return {"Authorization": f"Bearer {SER_REMOTE_TOKEN}"} if SER_REMOTE_TOKEN else {}


def is_available() -> bool:
    """True if the remote server is configured and reachable, and reports
    its own local SER backend as available (i.e. funasr loaded there)."""
    if not SER_REMOTE_URL:
        return False
    try:
        resp = requests.get(f"{_base_url()}/health", headers=_headers(), timeout=5.0)
    except requests.RequestException as exc:
        logger.warning("Remote SER health check failed: %s", exc)
        return False
    if resp.status_code != 200:
        logger.warning("Remote SER health check returned HTTP %s", resp.status_code)
        return False
    try:
        return bool(resp.json().get("ser_available", False))
    except ValueError:
        return False


def predict_zone_from_audio(audio_bytes: bytes, backend_id: str) -> tuple[str, dict[str, float]]:
    """Forward WAV bytes to the remote server's active backend and return
    (zone, probs), the same contract as the local backends.

    Raises:
        RuntimeError — endpoint unreachable, misconfigured, or the server
            itself could not run inference (mirrors the local ImportError/
            RuntimeError cases so callers need only one except clause).
    """
    if not SER_REMOTE_URL:
        raise RuntimeError("SER_REMOTE_URL is not configured.")
    try:
        resp = requests.post(
            f"{_base_url()}/predict",
            params={"backend": backend_id},
            files={"audio": ("audio.wav", audio_bytes, "audio/wav")},
            headers=_headers(),
            timeout=SER_REMOTE_TIMEOUT_S,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Remote SER endpoint unreachable: {exc}") from exc

    if resp.status_code != 200:
        raise RuntimeError(
            f"Remote SER inference failed (HTTP {resp.status_code}): {resp.text[:200]}"
        )

    data = resp.json()
    return data["zone"], data["probs"]
