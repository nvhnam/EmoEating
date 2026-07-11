"""
EmoEating SER inference server.

A thin FastAPI wrapper around the existing app/engine/ser_engine.py — the
SAME module, SAME backend code (_ser_crema.py / _ser_original.py), SAME
emotion2vec_plus_large model as local dev. Deploy this on a host with enough
RAM/disk to run funasr (Streamlit Community Cloud cannot), and point the main
Streamlit app at it via SER_REMOTE_URL so cloud deployments get identical SER
results to local ones — only the compute location changes.

Run locally:
    uvicorn server.main:app --host 0.0.0.0 --port 8000

Deploy: see server/README.md (HF Spaces Docker SDK, Render, Fly.io, or any VM).
"""

import io
import logging
import os
import struct
import sys
import threading
import wave
from typing import Optional

# app/ holds config.py, engine/, etc. as top-level importable modules — insert
# it onto sys.path exactly like app/pages/*.py does, so `import engine.ser_engine`
# and its internal `from config import ...` calls resolve unchanged.
_APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app")
sys.path.insert(0, os.path.abspath(_APP_DIR))

from fastapi import FastAPI, File, Header, HTTPException, Query, UploadFile  # noqa: E402

from engine import ser_engine  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ser_server")

# Shared-secret auth (matches SER_REMOTE_TOKEN on the client side). Leave
# SER_SERVER_TOKEN unset only for local testing — never in a public deploy.
_SERVER_TOKEN = os.getenv("SER_SERVER_TOKEN", "")

app = FastAPI(title="EmoEating SER Inference Server", version="1.0")


def _silence_wav_bytes(duration_s: float = 1.0, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack("<%dh" % int(sample_rate * duration_s), *([0] * int(sample_rate * duration_s))))
    return buf.getvalue()


def _warm_up_default_backend() -> None:
    """Load the default backend's model into memory once at startup, in the
    background, so the first real user request isn't the one that eats a
    30-120s cold model-load and risks exceeding the client's SER_REMOTE_TIMEOUT_S."""
    try:
        logger.info("Warming up default SER backend...")
        ser_engine.predict_zone_from_audio(_silence_wav_bytes())
        logger.info("SER backend warm-up complete.")
    except Exception:
        logger.exception("SER backend warm-up failed — first real request will load cold.")


@app.on_event("startup")
def _on_startup() -> None:
    threading.Thread(target=_warm_up_default_backend, daemon=True).start()


def _check_auth(authorization: Optional[str]) -> None:
    if not _SERVER_TOKEN:
        return
    expected = f"Bearer {_SERVER_TOKEN}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/health")
def health(authorization: Optional[str] = Header(None)) -> dict:
    """Unauthenticated-safe liveness probe; also reports whether funasr is
    actually loadable on this host so the client's is_available() reflects
    real state, not just process liveness."""
    try:
        available = ser_engine.is_available()
    except Exception as exc:  # defensive — never let a health check 500
        logger.exception("Health check failed while probing SER availability")
        return {"status": "ok", "ser_available": False, "error": str(exc)[:200]}
    return {"status": "ok", "ser_available": available}


@app.post("/predict")
async def predict(
    audio: UploadFile = File(...),
    backend: str = Query("crema4class"),
    authorization: Optional[str] = Header(None),
) -> dict:
    _check_auth(authorization)

    try:
        ser_engine.set_backend(backend)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    audio_bytes = await audio.read()

    try:
        zone, probs = ser_engine.predict_zone_from_audio(audio_bytes)
    except ImportError as exc:
        raise HTTPException(
            status_code=503, detail=f"SER backend unavailable on server: {exc}"
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=f"Inference failed: {exc}") from exc

    return {"zone": zone, "probs": probs, "backend": ser_engine.current_backend()}
