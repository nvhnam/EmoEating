# backend/api/ws_emotion.py
"""WebSocket /ws/emotion: streams Int16 PCM → RollingWindow → ConfidenceEngine → JSON."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from emoeating.config import MAX_CONCURRENT_WS_SESSIONS
from emoeating.voice.confidence import ConfidenceEngine
from emoeating.voice.stream import RollingWindow

ws_router = APIRouter()


def _make_engine(websocket: WebSocket) -> ConfidenceEngine:
    """Allow tests to inject a fast engine via app.state.create_engine factory."""
    factory = getattr(websocket.app.state, "create_engine", None)
    if factory is not None:
        return factory()
    return ConfidenceEngine()


@ws_router.websocket("/ws/emotion")
async def ws_emotion(websocket: WebSocket) -> None:  # noqa: PLR0912
    app = websocket.app

    # --- Origin allowlist check (CORS middleware does not cover WS upgrades) ---
    # Allow connections with no Origin header (same-origin tools, non-browser clients).
    origin = websocket.headers.get("origin")
    if origin is not None:
        settings = getattr(app.state, "settings", None)
        allowed = settings.cors_origins if settings is not None else ()
        if origin not in allowed:
            await websocket.close(code=4403)
            return

    await websocket.accept()

    # --- Concurrent session cap ---
    if not hasattr(app.state, "active_ws_sessions"):
        app.state.active_ws_sessions = 0
    max_sessions = getattr(app.state, "max_ws_sessions", MAX_CONCURRENT_WS_SESSIONS)
    if app.state.active_ws_sessions >= max_sessions:
        await websocket.close(code=4429)
        return

    app.state.active_ws_sessions += 1
    try:
        await _run_emotion_session(websocket)
    finally:
        app.state.active_ws_sessions = max(0, app.state.active_ws_sessions - 1)


async def _run_emotion_session(websocket: WebSocket) -> None:
    encoder = getattr(websocket.app.state, "encoder", None)
    if encoder is None:
        await websocket.close(code=4503)
        return

    engine = _make_engine(websocket)
    stream = RollingWindow(encoder=encoder, engine=engine)

    try:
        while True:
            try:
                msg = await websocket.receive()
            except WebSocketDisconnect:
                return

            if msg.get("type") == "websocket.disconnect":
                return

            raw_bytes: bytes | None = msg.get("bytes")
            raw_text: str | None = msg.get("text")

            if raw_bytes:
                # Offload CPU-bound encoding off the event loop so other sessions
                # and the token endpoint are not blocked during inference.
                states = await asyncio.to_thread(stream.push_pcm, raw_bytes)
                for state in states:
                    await websocket.send_json(
                        {
                            "type": "tick",
                            "confidence": state.confidence,
                            "elapsed": state.speech_elapsed,
                        }
                    )
                    if state.safety_flag:
                        await websocket.send_json({"type": "safety_flag"})
                    if state.decision == "STOP":
                        infer = engine.final_infer()
                        await websocket.send_json({"type": "done", "infer": infer})
                        return

            elif raw_text:
                try:
                    ctrl = json.loads(raw_text)
                except json.JSONDecodeError:
                    continue
                ctrl_type = ctrl.get("type")
                if ctrl_type == "agent_speaking":
                    stream.set_agent_speaking(bool(ctrl.get("value", False)))
                elif ctrl_type == "abort":
                    return

    except Exception:
        pass
