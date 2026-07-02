# backend/api/main.py
"""FastAPI application factory: CORS, startup wiring, real-vs-Null selection."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from emoeating.config import MAX_CONCURRENT_WS_SESSIONS, Settings, load_settings
from emoeating.data.store import FoodStore
from emoeating.external.images import (
    GoogleImageProvider,
    ImageProvider,
    NullImageProvider,
)
from emoeating.external.restaurants import (
    GooglePlacesProvider,
    NullRestaurantProvider,
    RestaurantProvider,
)
from emoeating.ser.encoder import Encoder
from api.realtime import realtime_router
from api.routes import router
from api.ws_emotion import ws_router


def build_image_provider(settings: Settings) -> ImageProvider:
    if settings.google_image_api_key and settings.google_image_cx:
        return GoogleImageProvider(settings.google_image_api_key, settings.google_image_cx)
    return NullImageProvider()


def build_restaurant_provider(settings: Settings) -> RestaurantProvider:
    if settings.google_places_api_key:
        return GooglePlacesProvider(settings.google_places_api_key)
    return NullRestaurantProvider()


def build_encoder(settings: Settings) -> Encoder | None:
    if not settings.emo_model_path:
        return None
    # Lazy import keeps funasr out of the module-load path.
    from emoeating.ser.encoder import Emotion2VecEncoder
    return Emotion2VecEncoder(model_id=settings.emo_model_path)


def build_store(settings: Settings) -> FoodStore | None:
    if not settings.store_path:
        return None
    try:
        return FoodStore.open(settings.store_path)
    except Exception:
        return None


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(title="EmoEating API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.image_provider = build_image_provider(settings)
    app.state.restaurant_provider = build_restaurant_provider(settings)
    app.state.encoder = build_encoder(settings)
    app.state.store = build_store(settings)

    # --- Voice-agent session state ---
    app.state.active_ws_sessions = 0
    app.state.max_ws_sessions = MAX_CONCURRENT_WS_SESSIONS
    app.state.realtime_rate_log: dict = {}

    # --- Routers ---
    app.include_router(router)         # existing HTTP routes
    app.include_router(ws_router)      # WS /ws/emotion
    app.include_router(realtime_router)  # POST /api/realtime/token

    return app
