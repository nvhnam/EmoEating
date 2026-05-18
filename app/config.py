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

# ── ENMS Recommendation parameters ──────────────────────────────────────────
TOP_K_DEFAULT     = 3      # default recommendations returned (formula_plan.md §4.6)
ENMS_ALPHA        = 0.7    # macro_score weight; tunable design parameter (document in paper)
DEFAULT_PREF_SCORE = 0.5   # neutral prior; no user history table yet

# Minimum data completeness to include food in scoring
MIN_DATA_COMPLETENESS = 5

# ── Stage 1: Physiological ────────────────────────────────────────────────────
# Mifflin-St Jeor (1990) activity multipliers
ACTIVITY_MULTIPLIERS = {
    "sedentary":       1.2,
    "lightly_active":  1.375,
    "moderately_active": 1.55,
}
# Per-meal energy fractions — USDA Dietary Guidelines 2020–2025
MEAL_ENERGY_FRACTION = {
    "breakfast": 0.25,
    "lunch":     0.35,
    "dinner":    0.30,
    "snack":     0.10,
}
DEFAULT_MEAL_KCAL = 600  # fallback when no profile; design parameter (document in paper)

# ── Stage 2: Zone classification ─────────────────────────────────────────────
# Russell (1980) circumplex. θ_neutral is a design parameter (document in paper).
THETA_NEUTRAL = 0.25
ZONE_LABELS = {
    "Q1_HAPPY":    "Happy / Energized",
    "Q2_STRESSED": "Stressed / Tense",
    "Q3_FATIGUED": "Fatigued / Low",
    "Q4_CONTENT":  "Content / Calm",
    "NEUTRAL":     "Neutral",
}
ZONE_COLORS = {
    "Q1_HAPPY":    "#FAC775",
    "Q2_STRESSED": "#F0997B",
    "Q3_FATIGUED": "#85B7EB",
    "Q4_CONTENT":  "#5DCAA5",
    "NEUTRAL":     "#888780",
}

# ── Stage 3: Zone → Macro ratios (within USDA AMDR bounds) ──────────────────
# Sources: Wurtman & Wurtman (1995), Benton (2002), Macht (2008), Jacka et al. (2017)
ZONE_MACRO_RATIOS = {
    "Q2_STRESSED": {"carb": 0.52, "prot": 0.22, "fat": 0.26},
    "Q3_FATIGUED": {"carb": 0.53, "prot": 0.22, "fat": 0.25},
    "Q1_HAPPY":    {"carb": 0.45, "prot": 0.28, "fat": 0.27},
    "Q4_CONTENT":  {"carb": 0.45, "prot": 0.22, "fat": 0.33},
    "NEUTRAL":     {"carb": 0.50, "prot": 0.22, "fat": 0.28},
}

# ── Stage 4: Zone-specific macro weights [w_carb, w_prot, w_fat] ─────────────
ZONE_MACRO_WEIGHTS = {
    "Q2_STRESSED": {"carb": 0.50, "prot": 0.30, "fat": 0.20},
    "Q3_FATIGUED": {"carb": 0.50, "prot": 0.30, "fat": 0.20},
    "Q1_HAPPY":    {"carb": 0.30, "prot": 0.45, "fat": 0.25},
    "Q4_CONTENT":  {"carb": 0.35, "prot": 0.30, "fat": 0.35},
    "NEUTRAL":     {"carb": 0.33, "prot": 0.34, "fat": 0.33},
}

# Portion defaults per food category (grams) — formula_plan.md §4.2
DEFAULT_PORTIONS_G = {
    "main_dish": 300, "side_dish": 150,
    "soup": 250, "stew": 250, "salad": 200,
}
DEFAULT_PORTION_G = 300  # fallback when category not matched

# ── Stage 5: Micronutrient display (informational only — NOT in ENMS score) ──
# Column names match food_nutrients DB columns exactly for direct lookup
ZONE_MICRONUTRIENT_PRIORITIES = {
    "Q2_STRESSED": ["magnesium_mg", "vitamin_b6_mg", "vitamin_c_mg", "omega3_mg"],
    "Q3_FATIGUED": ["folate_mcg", "vitamin_b12_mcg", "vitamin_d_mcg", "iron_mg"],
    "Q1_HAPPY":    ["vitamin_c_mg", "vitamin_e_mg", "magnesium_mg"],
    "Q4_CONTENT":  ["fiber_g", "omega3_mg"],
    "NEUTRAL":     [],
}
ZONE_EXPLANATIONS = {
    "Q2_STRESSED": (
        "For your stressed state, we prioritized complex carbs and foods rich in "
        "Magnesium and B6 to support cortisol regulation and serotonin synthesis."
    ),
    "Q3_FATIGUED": (
        "For your fatigued state, we prioritized energy-stabilizing complex carbs "
        "and foods with Folate, B12, and Vitamin D to support mood and energy."
    ),
    "Q1_HAPPY": (
        "For your energized state, we prioritized protein-forward options and "
        "antioxidants to support your elevated activity level."
    ),
    "Q4_CONTENT": (
        "For your relaxed state, we prioritized fiber-rich, healthy-fat foods "
        "to support your gut-brain axis and sustained calm."
    ),
    "NEUTRAL": "A balanced meal to sustain your current state.",
}

# RDA reference values for informational micronutrient display (NIH ODS DRI 2020)
# Keys match DB column names. Units: mg or mcg as column name suffix indicates.
RDA_REFERENCE = {
    "magnesium_mg":    {"male": 420,   "female": 320},
    "vitamin_b6_mg":   {"male": 1.7,   "female": 1.5},
    "vitamin_c_mg":    {"male": 90,    "female": 75},
    "folate_mcg":      {"male": 400,   "female": 400},
    "vitamin_b12_mcg": {"male": 2.4,   "female": 2.4},
    "vitamin_d_mcg":   {"male": 15.0,  "female": 15.0},
    "iron_mg":         {"male": 8,     "female": 18},
    "vitamin_e_mg":    {"male": 15,    "female": 15},    # mg/day (NIH ODS DRI 2020)
    "omega3_mg":       {"male": 1600,  "female": 1100},  # AI values (mg/day)
    "fiber_g":         {"male": 38,    "female": 25},    # AI values (g/day)
}

# Nutrient human-readable labels for UI display
NUTRIENT_DISPLAY_LABELS = {
    "magnesium_mg":    "Magnesium",
    "vitamin_b6_mg":   "Vitamin B6",
    "vitamin_c_mg":    "Vitamin C",
    "vitamin_e_mg":    "Vitamin E",
    "folate_mcg":      "Folate",
    "vitamin_b12_mcg": "Vitamin B12",
    "vitamin_d_mcg":   "Vitamin D",
    "iron_mg":         "Iron",
    "omega3_mg":       "Omega-3",
    "fiber_g":         "Dietary Fiber",
    "protein_g":       "Protein",
    "carbohydrate_g":  "Carbohydrates",
    "fat_g":           "Fat",
}

UI_DISCLAIMER = (
    "MoodMeal provides general meal suggestions based on mood and nutritional patterns. "
    "It does not provide medical or clinical dietary advice. "
    "Consult a registered dietitian for personalized health guidance."
)

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

# Meal type display labels
MEAL_TYPE_LABELS = {
    "breakfast": "Breakfast",
    "lunch":     "Lunch",
    "dinner":    "Dinner",
    "snack":     "Snack",
}

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

# ── Additional IP geolocation fallbacks (for Streamlit Cloud reliability) ────
GEOJS_ENDPOINT        = "https://get.geojs.io/v1/ip/geo/"
IPWHOIS_ENDPOINT      = "https://ipwhois.app/json/"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"

# ── Food image service ────────────────────────────────────────────────────────
FOOD_IMAGE_CACHE_TTL     = 3600
FOOD_IMAGE_COUNT         = 3
OPENFOODFACTS_SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"
WIKIPEDIA_API_URL        = "https://en.wikipedia.org/w/api.php"
WIKIMEDIA_API_URL        = "https://commons.wikimedia.org/w/api.php"
