# backend/tests/test_ws_emotion.py
"""WS /ws/emotion: tick/done flow, abort, agent gate, session cap. No OpenAI."""
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from emoeating.config import Settings
from emoeating.ser.encoder import MockEncoder
from emoeating.ser.labels import normalize_emotion_scores
from emoeating.voice.confidence import ConfidenceEngine
from api.main import create_app

SR = 16_000
WINDOW_N = 3 * SR

TEST_SETTINGS = Settings(
    google_image_api_key=None,
    google_image_cx=None,
    google_places_api_key=None,
    emo_model_path=None,
    store_path=None,
    cors_origins=("http://localhost:5173",),
)


def _sine_pcm(n_samples: int, amplitude: int = 4000) -> bytes:
    t = np.arange(n_samples, dtype=np.float32)
    sig = (amplitude * np.sin(2.0 * np.pi * 440 * t / SR)).astype(np.int16)
    return sig.tobytes()


@pytest.fixture
def ws_app():
    app = create_app(TEST_SETTINGS)
    # Inject MockEncoder that returns confident sad on every window.
    app.state.encoder = MockEncoder({"sad": 0.8, "neutral": 0.15, "other": 0.05})
    # Inject a fast engine so STOP fires within a few windows.
    app.state.create_engine = lambda: ConfidenceEngine(
        speech_floor_s=2.0, stability_n=2, margin_theta=0.05, timeout_s=9999.0
    )
    return app


@pytest.fixture
def ws_client(ws_app):
    return TestClient(ws_app)


# ---------------------------------------------------------------------------
# Test 1: tick then done
# ---------------------------------------------------------------------------

def test_ws_emotion_tick_then_done(ws_client):
    """Feeding enough loud PCM should produce tick(s) then a done with InferResult."""
    # Need 2 windows (floor=2s, hop=1s → 2 hops = 2s speech):
    # window_n + hop_n = 3*SR + 1*SR = 4*SR samples
    pcm = _sine_pcm(4 * SR)

    with ws_client.websocket_connect("/ws/emotion") as ws:
        ws.send_bytes(pcm)

        messages = []
        for _ in range(20):  # collect up to 20 messages
            try:
                msg = ws.receive_json()
                messages.append(msg)
                if msg.get("type") == "done":
                    break
            except Exception:
                break

    types = [m["type"] for m in messages]
    assert "tick" in types, f"No tick received; got: {types}"
    assert "done" in types, f"No done received; got: {types}"

    done_msg = next(m for m in messages if m["type"] == "done")
    infer = done_msg["infer"]
    assert set(infer) >= {"emotion_probs", "valence", "arousal", "zone"}
    assert infer["zone"] in {"POS_ACTIVE", "NEG_ACTIVE", "NEG_DEACTIVE", "NEUTRAL_CALM"}


# ---------------------------------------------------------------------------
# Test 2: abort closes cleanly without done
# ---------------------------------------------------------------------------

def test_ws_emotion_abort_no_done(ws_client):
    """Abort terminates the session; server must NOT emit done.

    Strategy (threading to avoid hang):
    - Receive window-1 tick to prove live communication.
    - Send abort + window-2 PCM (which would fire done if abort is ignored).
    - A daemon thread tries to collect the post-abort message for up to 1 second.
      Correct code:  abort returns before window-2 is processed → nothing arrives
                     → thread hangs → join(1.0) times out → no done collected.
      Broken code:   abort ignored → window-2 → done sent quickly → thread captures
                     it within 1 s → assertion fails.
    - __exit__ cancels the Starlette TestClient CancelScope, which closes the
      memory streams and unblocks the background thread so it exits cleanly.
    """
    import threading
    import queue as _queue

    post: _queue.Queue = _queue.Queue()

    with ws_client.websocket_connect("/ws/emotion") as ws:
        # Phase 1: window 1 → 1 tick (CONTINUE); blocking receive exits when tick arrives.
        ws.send_bytes(_sine_pcm(3 * SR))      # WINDOW_N samples
        first = ws.receive_json()             # terminates when server sends tick
        assert first.get("type") == "tick", f"Expected tick from window 1; got {first}"

        # Phase 2: abort + window-2 PCM.  Without abort, window 2 would fire done.
        ws.send_text(json.dumps({"type": "abort"}))
        ws.send_bytes(_sine_pcm(SR))          # HOP_N fills residual 2*SR → window 2 if not aborted

        # Collect post-abort messages in a daemon thread with a 1-second window.
        def _recv() -> None:
            try:
                while True:
                    post.put(("msg", ws.receive_json()))
            except Exception as e:
                post.put(("exc", e))

        t = threading.Thread(target=_recv, daemon=True)
        t.start()
        t.join(timeout=1.0)                   # 1 s: done (broken) arrives fast; correct times out

    # __exit__ calls cs.cancel() → closes streams → unblocks background thread.
    t.join()                                  # wait for thread to fully exit after stream close

    extra: list[dict] = []
    while not post.empty():
        kind, val = post.get_nowait()
        if kind == "msg":
            extra.append(val)

    done_msgs = [m for m in extra if m.get("type") == "done"]
    assert done_msgs == [], (
        f"done must not be sent after abort; got done_msgs={done_msgs}, extra={extra}"
    )


# ---------------------------------------------------------------------------
# Test 3: agent_speaking gate — no ticks while agent is speaking
# ---------------------------------------------------------------------------

def test_ws_emotion_agent_gate_drops_window(ws_app):
    """Windows while agent_speaking=True must be dropped; only non-agent windows emit ticks.

    Strategy (threading to avoid hang after abort):
      Phase 1 — agent_speaking=True  + WINDOW_N PCM → 1 dropped window   (0 ticks with gate)
      Phase 2 — agent_speaking=False + HOP_N=SR PCM → 1 processed window (1 tick always)
      Abort + daemon thread collects all post-phase-2 messages for 1 second.

    Buffer arithmetic: after Phase 1, RollingWindow residual = WINDOW_N - HOP_N = 2*SR.
    Phase 2 adds HOP_N = SR → fills to WINDOW_N → exactly one normal window fires.

    Correct code  (gate works):  agent window dropped → 1 tick total (phase-2 only).
    Broken code   (gate removed): agent window fires → 2 ticks total (phase-1 + phase-2).
    Assertion: exactly 1 tick. 2 ticks → FAIL.
    """
    import threading
    import queue as _queue

    ws_app.state.create_engine = lambda: ConfidenceEngine(
        speech_floor_s=999.0,  # prevent STOP; abort drives termination
        stability_n=10,
        margin_theta=0.05,
        timeout_s=9999.0,
    )
    client = TestClient(ws_app)
    post: _queue.Queue = _queue.Queue()

    with client.websocket_connect("/ws/emotion") as ws:
        # Phase 1: one full window while agent is speaking — must be dropped.
        ws.send_text(json.dumps({"type": "agent_speaking", "value": True}))
        ws.send_bytes(_sine_pcm(WINDOW_N))  # WINDOW_N = 3*SR; residual after hop = 2*SR

        # Phase 2: refill residual → exactly one normal window fires → 1 tick.
        ws.send_text(json.dumps({"type": "agent_speaking", "value": False}))
        ws.send_bytes(_sine_pcm(SR))        # HOP_N = SR; 2*SR + SR = WINDOW_N → 1 tick

        # Abort terminates the server handler; daemon thread collects all ticks.
        ws.send_text(json.dumps({"type": "abort"}))

        def _recv() -> None:
            try:
                while True:
                    post.put(("msg", ws.receive_json()))
            except Exception as e:
                post.put(("exc", e))

        t = threading.Thread(target=_recv, daemon=True)
        t.start()
        t.join(timeout=1.0)               # 1 s window: broken case gets 2 ticks quickly

    # __exit__ cancels CancelScope → closes streams → unblocks background thread.
    t.join()                              # wait for clean thread exit

    messages: list[dict] = []
    while not post.empty():
        kind, val = post.get_nowait()
        if kind == "msg":
            messages.append(val)

    tick_msgs = [m for m in messages if m.get("type") == "tick"]
    # Exactly 1 tick: Phase 2 only. If gate removed → Phase 1 also fires → 2 → FAIL.
    assert len(tick_msgs) == 1, (
        f"Expected exactly 1 tick (phase-2 only); got {len(tick_msgs)}: {messages}"
    )
    assert all(m.get("type") != "done" for m in messages), (
        f"done must not appear (speech_floor=999s prevents STOP); got {messages}"
    )


# ---------------------------------------------------------------------------
# Test 4: concurrent session cap
# ---------------------------------------------------------------------------

def test_ws_session_cap_closes_excess(ws_app):
    """When max_ws_sessions=0, any new connection is immediately closed."""
    ws_app.state.max_ws_sessions = 0
    client = TestClient(ws_app)
    closed = False
    try:
        with client.websocket_connect("/ws/emotion") as ws:
            # Server should accept then immediately close (cap exceeded).
            msg = ws.receive()
            if msg.get("type") == "websocket.close":
                closed = True
    except Exception:
        closed = True
    assert closed, "Expected connection to be closed when cap is 0"


# ---------------------------------------------------------------------------
# Test 5: safety_flag message emitted before done
# ---------------------------------------------------------------------------

def test_ws_emotion_safety_flag_emitted(ws_app):
    # Override engine with very low safety threshold so it fires immediately.
    ws_app.state.create_engine = lambda: ConfidenceEngine(
        speech_floor_s=2.0, stability_n=2, margin_theta=0.05,
        timeout_s=9999.0, safety_neg_threshold=0.01,  # always fires
    )
    # Strong NEG encoder to push neg zone mass high.
    ws_app.state.encoder = MockEncoder({"angry": 0.5, "fearful": 0.3, "sad": 0.2})
    client = TestClient(ws_app)
    pcm = _sine_pcm(4 * SR)
    with client.websocket_connect("/ws/emotion") as ws:
        ws.send_bytes(pcm)
        messages = []
        for _ in range(20):
            try:
                msg = ws.receive_json()
                messages.append(msg)
                if msg.get("type") == "done":
                    break
            except Exception:
                break

    types = [m["type"] for m in messages]
    assert "safety_flag" in types, f"Expected safety_flag in {types}"


# ---------------------------------------------------------------------------
# Test 6: Origin allowlist validation (Fix 2)
# ---------------------------------------------------------------------------

def test_ws_origin_disallowed_rejected(ws_app):
    """A connection with a disallowed Origin header must be rejected (closed 4403)."""
    client = TestClient(ws_app)
    closed = False
    try:
        with client.websocket_connect(
            "/ws/emotion", headers={"origin": "http://evil.com"}
        ) as ws:
            msg = ws.receive()
            if msg.get("type") == "websocket.close":
                closed = True
    except Exception:
        closed = True
    assert closed, "Expected connection to be rejected for disallowed origin"


def test_ws_origin_allowed_connects(ws_app):
    """A connection with a whitelisted Origin header must connect normally."""
    # ws_app uses TEST_SETTINGS with cors_origins=("http://localhost:5173",)
    client = TestClient(ws_app)
    with client.websocket_connect(
        "/ws/emotion", headers={"origin": "http://localhost:5173"}
    ) as ws:
        # Send abort immediately — server exits cleanly without error
        ws.send_text(json.dumps({"type": "abort"}))
