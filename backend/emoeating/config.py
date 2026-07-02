"""Tunable constants and lookup tables for EmoEating.

The emotion->valence/arousal table, AMDR macro ratios, and per-meal RDA targets
are design choices grounded in the cited literature (Russell 1980; USDA DRI);
they are intended to be tuned, not treated as ground truth.
"""

# --- ENMS weights and zone threshold (spec section 6.4) ---
ALPHA: float = 0.55
BETA: float = 0.20
GAMMA: float = 0.25
THETA: float = 0.25

MEAL_FRACTION: float = 1.0 / 3.0   # one meal targets ~1/3 of daily intake
DEFAULT_MEAL_KCAL: float = 600.0   # used when no physiological profile is given

# --- Emotion -> (valence, arousal) on [-1, 1], dominant-class placement ---
# emotion2vec+_large 9-class label set. Coordinates from Russell's circumplex norms.
EMOTION_VA: dict[str, tuple[float, float]] = {
    "happy":     (0.80,  0.50),
    "angry":     (-0.70, 0.70),
    "sad":       (-0.70, -0.50),
    "fearful":   (-0.60, 0.60),
    "disgusted": (-0.60, 0.30),
    "surprised": (0.30,  0.70),
    "neutral":   (0.00,  0.00),
    "other":     (0.00,  0.00),   # abstain -> neutral/calm baseline
    "unknown":   (0.00,  0.00),   # abstain -> neutral/calm baseline
}

# --- Per-zone macro energy split (fraction of meal kcal), within USDA AMDR ---
ZONE_MACRO_RATIOS: dict[str, dict[str, float]] = {
    "POS_ACTIVE":   {"protein": 0.25, "carb": 0.50, "fat": 0.25},
    "NEG_ACTIVE":   {"protein": 0.30, "carb": 0.45, "fat": 0.25},
    "NEG_DEACTIVE": {"protein": 0.25, "carb": 0.50, "fat": 0.25},
    "NEUTRAL_CALM": {"protein": 0.20, "carb": 0.55, "fat": 0.25},
}

# --- Per-zone priority micronutrients (canonical keys; spec Table 1) ---
ZONE_PRIORITY_MICROS: dict[str, list[str]] = {
    "POS_ACTIVE":   ["vit_c_mg", "vit_e_mg"],
    "NEG_ACTIVE":   ["magnesium_mg", "vit_b6_mg", "vit_c_mg"],
    "NEG_DEACTIVE": ["folate_ug", "vit_b12_ug", "vit_d_ug", "omega3_g"],
    "NEUTRAL_CALM": ["fiber_g", "omega3_g"],
}

# --- Adult daily RDA per micronutrient (USDA DRI); per-meal target = RDA * MEAL_FRACTION ---
MICRO_RDA: dict[str, float] = {
    "vit_c_mg": 90.0,
    "vit_e_mg": 15.0,
    "magnesium_mg": 400.0,
    "vit_b6_mg": 1.3,
    "folate_ug": 400.0,
    "vit_b12_ug": 2.4,
    "vit_d_ug": 15.0,
    "omega3_g": 1.6,
    "fiber_g": 28.0,
}

# --- Mifflin-St Jeor activity multipliers ---
ACTIVITY_FACTORS: dict[str, float] = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}

# ---------------------------------------------------------------------------
# Voice agent — ConfidenceEngine tunable knobs
# ---------------------------------------------------------------------------
WINDOW_S: float = 3.0          # rolling window length in seconds
HOP_S: float = 1.0             # hop between consecutive windows
EMA_ALPHA: float = 0.3         # EMA smoothing factor (higher = faster adaptation)
MIN_WINDOW_CONF: float = 0.35  # dominant-prob floor; windows below this are skipped
SPEECH_FLOOR_S: float = 18.0   # minimum quality speech-time before early STOP
STABILITY_N: int = 5           # leading-zone must be stable for this many windows
MARGIN_THETA: float = 0.15     # min gap between leading and second zone mass
TIMEOUT_S: float = 90.0        # wall-clock timeout → best-so-far STOP
SAFETY_NEG_THRESHOLD: float = 0.8  # combined NEG zone mass that triggers safety_flag
MAX_CONCURRENT_WS_SESSIONS: int = 10  # cap on simultaneous /ws/emotion connections


def _compute_emotion_zone() -> dict[str, str]:
    """Precompute label → zone by delegating to the canonical affect functions.

    Imported here (not at module top) so config finishes defining EMOTION_VA/THETA
    before affect.* (which import those names) load — avoids a circular import.
    """
    from emoeating.affect.mapping import to_valence_arousal
    from emoeating.affect.zones import assign_zone
    return {
        label: assign_zone(*to_valence_arousal({label: 1.0})).value
        for label in EMOTION_VA
    }


EMOTION_ZONE: dict[str, str] = _compute_emotion_zone()

import os
from dataclasses import dataclass

from dotenv import find_dotenv, load_dotenv


@dataclass(frozen=True)
class Settings:
    """Server-side configuration. API keys live here and never leave the backend."""
    # --- existing fields (required, no default) ---
    google_image_api_key: str | None
    google_image_cx: str | None
    google_places_api_key: str | None
    emo_model_path: str | None
    store_path: str | None
    cors_origins: tuple[str, ...]
    # --- voice agent fields (optional, have defaults) ---
    openai_api_key: str | None = None
    openai_realtime_model: str = "gpt-4o-realtime-preview"
    openai_realtime_voice: str = "alloy"
    realtime_rate_per_user: int = 5
    # --- provider selection + Gemini Live ---
    voice_provider: str = "openai"  # "openai" | "gemini"
    google_api_key: str | None = None
    gemini_live_model: str = "gemini-3.1-flash-live-preview"
    gemini_voice: str = "Aoede"  # VERIFY voice id against current Gemini Live docs
    # v1alpha Live WS endpoint. MUST be the *Constrained* method — ephemeral tokens
    # only work there; plain BidiGenerateContent needs a full API key. VERIFY vs docs.
    gemini_ws_url: str = (
        "wss://generativelanguage.googleapis.com/ws/"
        "google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContentConstrained"
    )


def load_settings() -> Settings:
    # Dev convenience: load a local .env if present (searches up from the cwd).
    # Real environment variables take precedence (override=False), so prod/CI
    # behavior is unchanged and secrets never need to live in the shell history.
    load_dotenv(find_dotenv(usecwd=True))
    origins_raw = os.environ.get("EMOEATING_CORS_ORIGINS", "http://localhost:5173")
    origins = tuple(o.strip() for o in origins_raw.split(",") if o.strip())
    return Settings(
        google_image_api_key=os.environ.get("EMOEATING_GOOGLE_IMAGE_API_KEY"),
        google_image_cx=os.environ.get("EMOEATING_GOOGLE_IMAGE_CX"),
        google_places_api_key=os.environ.get("EMOEATING_GOOGLE_PLACES_API_KEY"),
        emo_model_path=os.environ.get("EMOEATING_MODEL_PATH"),
        store_path=os.environ.get("EMOEATING_STORE_PATH"),
        cors_origins=origins,
        openai_api_key=os.environ.get("EMOEATING_OPENAI_API_KEY"),
        openai_realtime_model=os.environ.get(
            "EMOEATING_OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview"
        ),
        openai_realtime_voice=os.environ.get(
            "EMOEATING_OPENAI_REALTIME_VOICE", "alloy"
        ),
        realtime_rate_per_user=int(
            os.environ.get("EMOEATING_REALTIME_RATE_PER_USER", "5")
        ),
        voice_provider=os.environ.get("EMOEATING_VOICE_PROVIDER", "openai"),
        google_api_key=os.environ.get("EMOEATING_GOOGLE_API_KEY"),
        gemini_live_model=os.environ.get(
            "EMOEATING_GEMINI_LIVE_MODEL", "gemini-3.1-flash-live-preview"
        ),
        gemini_voice=os.environ.get("EMOEATING_GEMINI_VOICE", "Aoede"),
        gemini_ws_url=os.environ.get(
            "EMOEATING_GEMINI_WS_URL",
            "wss://generativelanguage.googleapis.com/ws/"
            "google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContentConstrained",
        ),
    )
