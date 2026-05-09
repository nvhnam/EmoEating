from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

# Emotion → (Valence, Arousal) mapping — Russell Circumplex (1980)
EMOTION_COORDS = {
    "happy":    {"V":  0.80, "A":  0.60, "emoji": "😊", "color": "#FAC775"},
    "excited":  {"V":  0.70, "A":  0.85, "emoji": "🤩", "color": "#F09595"},
    "content":  {"V":  0.70, "A": -0.30, "emoji": "🙂", "color": "#5DCAA5"},
    "calm":     {"V":  0.65, "A": -0.55, "emoji": "😌", "color": "#1D9E75"},
    "neutral":  {"V":  0.00, "A":  0.00, "emoji": "😐", "color": "#888780"},
    "bored":    {"V": -0.20, "A": -0.70, "emoji": "😒", "color": "#B4B2A9"},
    "tired":    {"V": -0.30, "A": -0.80, "emoji": "😴", "color": "#6B6B67"},
    "sad":      {"V": -0.70, "A": -0.55, "emoji": "😢", "color": "#85B7EB"},
    "anxious":  {"V": -0.55, "A":  0.65, "emoji": "😰", "color": "#AFA9EC"},
    "stressed": {"V": -0.60, "A":  0.70, "emoji": "😤", "color": "#F0997B"},
    "angry":    {"V": -0.80, "A":  0.80, "emoji": "😠", "color": "#E24B4A"},
}

# Recommendation weights
AFFECTIVE_WEIGHT = 0.70
CALORIC_WEIGHT   = 0.30
TOP_K_DEFAULT    = 5

# Caloric tolerance: ±60% of per-meal target (wide tolerance for variety)
CALORIC_TOLERANCE = 0.60

# Minimum data completeness to include food in scoring
MIN_DATA_COMPLETENESS = 5

# DB connection — override via environment variables
DB_HOST = os.getenv("MOODMEAL_DB_HOST", "localhost")
DB_PORT = int(os.getenv("MOODMEAL_DB_PORT", "3306"))
DB_NAME = os.getenv("MOODMEAL_DB_NAME", "moodmeal")
DB_USER = os.getenv("MOODMEAL_DB_USER", "root")
DB_PASS = os.getenv("MOODMEAL_DB_PASS", "")

# Vietnamese dataset feature flag
# true  → app connects to moodmeal_vn (Vietnamese food data)
# false → app connects to moodmeal (original multi-dataset)
USE_VN_DATA = os.getenv("USE_VN_DATA", "false").strip().lower() in ("1", "true", "yes")
VN_DB_NAME  = os.getenv("MOODMEAL_VN_DB_NAME", "moodmeal_vn")

# Activity multiplier: sedentary post-work home scenario (Mifflin-St Jeor 1990)
ACTIVITY_MULTIPLIER = 1.2

# Meals per day for per-meal caloric target
MEALS_PER_DAY = 3

# Meal type display labels
MEAL_TYPE_LABELS = {
    "breakfast": "Breakfast",
    "lunch":     "Lunch",
    "dinner":    "Dinner",
    "snack":     "Snack",
}

# Nutrient bar display order and labels
NUTRIENT_DISPLAY = [
    ("tryptophan",    "Tryptophan (serotonin)"),
    ("omega3",        "Omega-3"),
    ("complex_carbs", "Complex Carbs"),
    ("magnesium",     "Magnesium"),
    ("iron",          "Iron"),
    ("b_vitamins",    "B Vitamins"),
    ("antioxidants",  "Antioxidants"),
    ("protein",       "Protein"),
    ("fiber",         "Fiber"),
    ("sugar_penalty", "Sugar (penalty)"),
]

# ── Nearby Restaurants Feature ───────────────────────────────────────────────
GOOGLE_PLACES_API_KEY          = os.getenv("GOOGLE_PLACES_API_KEY", "")
FOURSQUARE_API_KEY             = os.getenv("FOURSQUARE_API_KEY", "")
HERE_API_KEY                   = os.getenv("HERE_API_KEY", "")
RESTAURANT_SEARCH_RADIUS_M     = int(os.getenv("RESTAURANT_SEARCH_RADIUS_M", "2000"))
RESTAURANT_MAX_RESULTS         = int(os.getenv("RESTAURANT_MAX_RESULTS", "4"))
RESTAURANT_CACHE_TTL           = 3600          # seconds for @st.cache_data

# Composite ranking weights: R = α·proximity + β·rating + γ·availability
# Documented in paper §4.3; externalized for ablation experiments.
RESTAURANT_SCORE_WEIGHTS = {"alpha": 0.50, "beta": 0.30, "gamma": 0.20}

# ipapi.co endpoint — get_ip_location() constructs URL as f"https://ipapi.co/{client_ip}/json/"
# after extracting the real client IP from the X-Forwarded-For header.
IPAPI_ENDPOINT                 = "https://ipapi.co/"
GOOGLE_PLACES_TEXT_SEARCH_URL  = "https://places.googleapis.com/v1/places:searchText"
FOURSQUARE_SEARCH_URL          = "https://places-api.foursquare.com/places/search"  # migrated from api.foursquare.com/v3/
HERE_SEARCH_URL                = "https://discover.search.hereapi.com/v1/discover"
# HERE_SEARCH_URL                = "https://geocode.search.hereapi.com/v1/geocode"
# HTTPS endpoint — avoids mixed-content issues on HTTPS-hosted Streamlit Cloud.
OSM_OVERPASS_URL               = "https://overpass-api.de/api/interpreter"
