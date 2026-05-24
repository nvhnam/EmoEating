from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

# ── Emotion → (Valence, Arousal) mapping — Russell Circumplex (1980) ─────────
# UI manual-selection emotions. VA coordinates used for zone classification
# and circumplex visualisation. SER path bypasses this table (direct zone lookup).
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

# ── ENMS scoring weights (3-component hybrid formula) ────────────────────────
# ENMS(F, Z, U) = α·macro_score + β·micro_score + γ·pref_score
# α + β + γ = 1.0  (author-designed weighting; future empirical calibration)
TOP_K_DEFAULT      = 3     # default recommendations returned
ENMS_MACRO_ALPHA   = 0.55  # macro_score weight (α)
ENMS_MICRO_BETA    = 0.20  # micro_score weight (β) — zone-priority micronutrient fulfillment
# γ = 1 - ENMS_MACRO_ALPHA - ENMS_MICRO_BETA = 0.25
DEFAULT_PREF_SCORE = 0.5   # neutral prior; no user interaction history yet

# Minimum data completeness to include food in scoring
MIN_DATA_COMPLETENESS = 5

# ── Stage 1: Physiological ────────────────────────────────────────────────────
# Mifflin-St Jeor (1990) activity multipliers — USDA DGA 2020-2025
ACTIVITY_MULTIPLIERS = {
    "sedentary":          1.2,    # default
    "lightly_active":     1.375,
    "moderately_active":  1.55,
}
# Per-meal energy fractions — USDA Dietary Guidelines 2020–2025
MEAL_ENERGY_FRACTION = {
    "breakfast": 0.25,
    "lunch":     0.35,
    "dinner":    0.30,
    "snack":     0.10,
}
DEFAULT_MEAL_KCAL = 600  # fallback when no physiological profile provided

# ── Stage 2: Zone classification — 4-zone reframe (guide.md Phase 2) ─────────
# Russell (1980) circumplex. Prior Q4 (positive deactivation / calm) is merged
# into NEUTRAL_BASELINE: valence at low arousal is the least recoverable
# affective dimension from prosody-only SER (Posner, Russell & Peterson 2005).
# θ_neutral is a design parameter documented in the paper.
THETA_NEUTRAL = 0.25

ZONE_LABELS = {
    "Q1_POS_ACT":       "Positive Activation",    # happy, excited — +V, +A
    "Q2_NEG_ACT":       "Negative Activation",    # stressed, anxious, angry — −V, +A
    "Q3_NEG_DEACT":     "Negative Deactivation",  # tired, sad, bored — −V, −A
    "NEUTRAL_BASELINE": "Neutral Baseline",        # neutral, calm, content
}
ZONE_COLORS = {
    "Q1_POS_ACT":       "#FAC775",   # warm amber
    "Q2_NEG_ACT":       "#F0997B",   # stressed orange-red
    "Q3_NEG_DEACT":     "#85B7EB",   # cool blue — fatigued/low
    "NEUTRAL_BASELINE": "#888780",   # neutral grey
}

# ── SER (Phase 1) — emotion2vec_plus_large → zone lookup ─────────────────────
# FunASR AutoModel inference: 16 kHz mono WAV → 9-class softmax → argmax → zone.
# Ma et al. (2024), Findings of ACL 2024. DOI: 10.18653/v1/2024.findings-acl.931
SER_MODEL_ID = "iic/emotion2vec_plus_large"
SER_EMOTION_CLASSES = [
    "angry", "disgusted", "fearful", "happy",
    "neutral", "other", "sad", "surprised", "unknown",
]
# Canonical 4-zone lookup — single source of truth per guide.md Phase 2 & 6.
SER_EMOTION_TO_ZONE: dict[str, str] = {
    "happy":     "Q1_POS_ACT",
    "surprised": "Q1_POS_ACT",
    "angry":     "Q2_NEG_ACT",
    "disgusted": "Q2_NEG_ACT",
    "fearful":   "Q2_NEG_ACT",
    "sad":       "Q3_NEG_DEACT",
    "neutral":   "NEUTRAL_BASELINE",
    "other":     "NEUTRAL_BASELINE",
    "unknown":   "NEUTRAL_BASELINE",
}

# ── Stage 3: Zone → Macro ratios (within USDA AMDR bounds) ──────────────────
# Carb 45–65%, Protein 10–35%, Fat 20–35% per USDA DGA 2020-2025.
# Zone-specific positioning is a design choice motivated by cited mechanisms —
# NOT quoted prescriptions from any single paper. Frame this in the paper.
# All rows sum to 1.0.
ZONE_MACRO_RATIOS = {
    "Q1_POS_ACT":       {"carb": 0.45, "prot": 0.27, "fat": 0.28},  # Macht 2008
    "Q2_NEG_ACT":       {"carb": 0.52, "prot": 0.22, "fat": 0.26},  # Wurtman 1995; Gómez-Pinilla 2008
    "Q3_NEG_DEACT":     {"carb": 0.52, "prot": 0.24, "fat": 0.24},  # Benton 2002; Gómez-Pinilla 2008
    "NEUTRAL_BASELINE": {"carb": 0.45, "prot": 0.22, "fat": 0.33},  # Jacka 2017 SMILES (Mediterranean)
}

# ── Stage 4: Zone-specific macro weights [w_carb, w_prot, w_fat] ─────────────
# Author-designed; weights sum to 1.0 per zone.
ZONE_MACRO_WEIGHTS = {
    "Q1_POS_ACT":       {"carb": 0.30, "prot": 0.45, "fat": 0.25},
    "Q2_NEG_ACT":       {"carb": 0.50, "prot": 0.30, "fat": 0.20},
    "Q3_NEG_DEACT":     {"carb": 0.50, "prot": 0.30, "fat": 0.20},
    "NEUTRAL_BASELINE": {"carb": 0.35, "prot": 0.30, "fat": 0.35},
}

# Portion defaults per food category (grams)
DEFAULT_PORTIONS_G = {
    "main_dish": 300, "side_dish": 150,
    "soup": 250, "stew": 250, "salad": 200,
}
DEFAULT_PORTION_G = 300  # fallback when category not matched

# ── Stage 5: Zone-priority micronutrients (scored in ENMS β component) ───────
# Every zone has |N_Z| ≥ 2 (guide.md Phase 4.2) — no empty priority set.
# NULL DB values → actual_n = 0 (conservative; no penalty, no reward).
# Column names match food_nutrients DB columns exactly.
# Sources: Boyle 2017; Wurtman 1995; Kennedy 2016; Jacka 2017; Gómez-Pinilla 2008; Cryan 2019.
ZONE_MICRONUTRIENT_PRIORITIES = {
    "Q1_POS_ACT":       ["vitamin_c_mg", "vitamin_e_mg"],                             # Gómez-Pinilla 2008
    "Q2_NEG_ACT":       ["magnesium_mg", "vitamin_b6_mg", "vitamin_c_mg"],            # Boyle 2017; Wurtman 1995; Gómez-Pinilla 2008
    "Q3_NEG_DEACT":     ["folate_mcg", "vitamin_b12_mcg", "vitamin_d_mcg", "omega3_mg"],  # Kennedy 2016; Jacka 2017; Gómez-Pinilla 2008
    "NEUTRAL_BASELINE": ["fiber_g", "omega3_mg"],                                     # Jacka 2017; Cryan 2019
}

ZONE_EXPLANATIONS = {
    "Q1_POS_ACT": (
        "Your ENMS score rewards antioxidant-rich foods (Vitamin C, E) alongside "
        "protein-forward options — adequate carbohydrates without excess "
        "(emotion-eating risk in positive high-arousal, Macht 2008). "
        "Protein sustains your elevated metabolic state."
    ),
    "Q2_NEG_ACT": (
        "Your ENMS score rewards foods with Magnesium, B6, and Vitamin C "
        "(cortisol regulation and serotonin synthesis — Boyle 2017; Wurtman & Wurtman 1995; "
        "Gómez-Pinilla 2008). Complex carbs drive tryptophan uptake → serotonin synthesis."
    ),
    "Q3_NEG_DEACT": (
        "Your ENMS score rewards foods with Folate, B12, Vitamin D, and Omega-3 "
        "(depressive-symptom support — Kennedy 2016; Jacka et al. 2017; Gómez-Pinilla 2008). "
        "Low-GI complex carbs → stable blood glucose → mood stabilisation (Benton 2002)."
    ),
    "NEUTRAL_BASELINE": (
        "Your ENMS score rewards a Mediterranean-style maintenance pattern — "
        "fiber-rich foods (gut–brain axis, Cryan et al. 2019) and omega-3 ALA "
        "(reduced depressive symptoms, Jacka et al. 2017 SMILES trial)."
    ),
}

# RDA reference values — NIH ODS DRI 2020. Keys match DB column names.
# Used for per-meal target_n(U) = RDA_REFERENCE[n][sex] × meal_fraction.
RDA_REFERENCE = {
    "magnesium_mg":    {"male": 420,   "female": 320},
    "vitamin_b6_mg":   {"male": 1.7,   "female": 1.5},
    "vitamin_c_mg":    {"male": 90,    "female": 75},
    "folate_mcg":      {"male": 400,   "female": 400},
    "vitamin_b12_mcg": {"male": 2.4,   "female": 2.4},
    "vitamin_d_mcg":   {"male": 15.0,  "female": 15.0},
    "iron_mg":         {"male": 8,     "female": 18},
    "vitamin_e_mg":    {"male": 15,    "female": 15},
    "omega3_mg":       {"male": 1600,  "female": 1100},  # AI values (mg/day)
    "fiber_g":         {"male": 38,    "female": 25},    # AI values (g/day)
}

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

# ── Database connection ───────────────────────────────────────────────────────
DB_HOST = os.getenv("MOODMEAL_DB_HOST", "localhost")
DB_PORT = int(os.getenv("MOODMEAL_DB_PORT", "3306"))
DB_NAME = os.getenv("MOODMEAL_DB_NAME", "moodmeal")
DB_USER = os.getenv("MOODMEAL_DB_USER", "root")
DB_PASS = os.getenv("MOODMEAL_DB_PASS", "")

USE_VN_DATA = os.getenv("USE_VN_DATA", "false").strip().lower() in ("1", "true", "yes")
VN_DB_NAME  = os.getenv("MOODMEAL_VN_DB_NAME", "moodmeal_vn")

MEAL_TYPE_LABELS = {
    "breakfast": "Breakfast",
    "lunch":     "Lunch",
    "dinner":    "Dinner",
    "snack":     "Snack",
}

# ── Nearby Restaurants ────────────────────────────────────────────────────────
GOOGLE_PLACES_API_KEY      = os.getenv("GOOGLE_PLACES_API_KEY", "")
FOURSQUARE_API_KEY         = os.getenv("FOURSQUARE_API_KEY", "")
HERE_API_KEY               = os.getenv("HERE_API_KEY", "")
RESTAURANT_SEARCH_RADIUS_M = int(os.getenv("RESTAURANT_SEARCH_RADIUS_M", "2000"))
RESTAURANT_MAX_RESULTS     = int(os.getenv("RESTAURANT_MAX_RESULTS", "4"))
RESTAURANT_CACHE_TTL       = 3600

RESTAURANT_SCORE_WEIGHTS = {"alpha": 0.50, "beta": 0.30, "gamma": 0.20}

IPAPI_ENDPOINT                = "https://ipapi.co/"
GOOGLE_PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
FOURSQUARE_SEARCH_URL         = "https://places-api.foursquare.com/places/search"
HERE_SEARCH_URL               = "https://discover.search.hereapi.com/v1/discover"
OSM_OVERPASS_URL              = "https://overpass-api.de/api/interpreter"

GEOJS_ENDPOINT        = "https://get.geojs.io/v1/ip/geo/"
IPWHOIS_ENDPOINT      = "https://ipwhois.app/json/"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"

# ── Food image service ────────────────────────────────────────────────────────
FOOD_IMAGE_CACHE_TTL     = 3600
FOOD_IMAGE_COUNT         = 3
OPENFOODFACTS_SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"
WIKIPEDIA_API_URL        = "https://en.wikipedia.org/w/api.php"
WIKIMEDIA_API_URL        = "https://commons.wikimedia.org/w/api.php"
