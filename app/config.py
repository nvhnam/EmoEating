from __future__ import annotations

import os
from dotenv import load_dotenv

from theme import ZONE_PALETTE, MACRO_COLORS

load_dotenv()

# ── Emotion → (Valence, Arousal) mapping — Russell Circumplex (1980) ─────────
# UI manual-selection emotions. VA coordinates used for zone classification
# and circumplex visualisation. SER path bypasses this table (direct zone lookup).
#
# "color" is each emotion's zone accent (app/theme.py::ZONE_PALETTE), NOT a
# per-emotion hue — every emotion in the same zone shares one color so the
# zone stays visually traceable across pages (selector → circumplex → recs
# context panel → methodology tables). The face icon (app/utils/icons.py)
# is what visually distinguishes emotions within a zone.
# Zone assignment mirrors engine/zone_classifier.py::classify_zone exactly:
#   magnitude<THETA_NEUTRAL -> NEUTRAL_BASELINE; V<=0,A>=0 -> Q2_NEG_ACT;
#   V<=0,A<0 -> Q3_NEG_DEACT; V>0,A>=0 -> Q1_POS_ACT; V>0,A<0 -> NEUTRAL_BASELINE.
EMOTION_COORDS = {
    "happy":    {"V":  0.80, "A":  0.60, "emoji": "😊", "color": ZONE_PALETTE["Q1_POS_ACT"]["accent"]},
    "excited":  {"V":  0.70, "A":  0.85, "emoji": "🤩", "color": ZONE_PALETTE["Q1_POS_ACT"]["accent"]},
    "content":  {"V":  0.70, "A": -0.30, "emoji": "🙂", "color": ZONE_PALETTE["NEUTRAL_BASELINE"]["accent"]},
    "calm":     {"V":  0.65, "A": -0.55, "emoji": "😌", "color": ZONE_PALETTE["NEUTRAL_BASELINE"]["accent"]},
    "neutral":  {"V":  0.00, "A":  0.00, "emoji": "😐", "color": ZONE_PALETTE["NEUTRAL_BASELINE"]["accent"]},
    "bored":    {"V": -0.20, "A": -0.70, "emoji": "😒", "color": ZONE_PALETTE["Q3_NEG_DEACT"]["accent"]},
    "tired":    {"V": -0.30, "A": -0.80, "emoji": "😴", "color": ZONE_PALETTE["Q3_NEG_DEACT"]["accent"]},
    "sad":      {"V": -0.70, "A": -0.55, "emoji": "😢", "color": ZONE_PALETTE["Q3_NEG_DEACT"]["accent"]},
    "anxious":  {"V": -0.55, "A":  0.65, "emoji": "😰", "color": ZONE_PALETTE["Q2_NEG_ACT"]["accent"]},
    "stressed": {"V": -0.60, "A":  0.70, "emoji": "😤", "color": ZONE_PALETTE["Q2_NEG_ACT"]["accent"]},
    "angry":    {"V": -0.80, "A":  0.80, "emoji": "😠", "color": ZONE_PALETTE["Q2_NEG_ACT"]["accent"]},
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
NUTRIENT_NULL = False  # False → exclude foods missing ANY zone-required micronutrient; True → no filter

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
    "Q3_NEG_DEACT":     "Negative Deactivated",   # tired, sad, bored — −V, −A
    "NEUTRAL_BASELINE": "Neutral Baseline",        # neutral, calm, content
}
# Legacy single-hex-per-zone contract (existing call sites use ZONE_COLORS[zone]
# as a plain string) — sourced from ZONE_PALETTE's accent step. Components that
# need the AA-legible text color or a panel tint should use ZONE_PALETTE directly.
ZONE_COLORS = {zone: ramp["accent"] for zone, ramp in ZONE_PALETTE.items()}

# ── SER (Phase 1 & 7) — emotion2vec_plus_seed → zone lookup ──────────────────
# FunASR AutoModel inference: 16 kHz mono WAV → class softmax → zone.
# Ma et al. (2024), Findings of ACL 2024. DOI: 10.18653/v1/2024.findings-acl.931
#
# Backend selection:
#   "original"    — 9-class off-the-shelf (uses the model's own built-in
#                    classification head; works with ANY emotion2vec+ size)
#   "crema4class" — CREMA-D 4-class linear probe (Phase 7; val WA=92.9%,
#                    CCC=0.83) — NOTE: that probe (app/models/best_linear_probe.pt)
#                    was trained on 1024-d embeddings from emotion2vec_plus_large
#                    specifically (see app/models/linear_probe_config.json).
#                    It is NOT compatible with a different-sized backbone and
#                    will raise at load time rather than silently mis-predict
#                    (see _ser_crema.py's dimension check) — retrain a new
#                    probe before re-enabling it against a different SER_MODEL_ID.
#
# SER_MODEL_ID is intentionally the smaller "seed" variant (~1.0 GB checkpoint,
# vs. ~1.9 GB for "large") together with the size-agnostic "original" backend,
# so the whole SER stack can run in-process on Streamlit Community Cloud's
# free-tier RAM budget instead of needing the separate server/ (see below).
SER_BACKEND  = "original"
SER_MODEL_ID = "iic/emotion2vec_plus_seed"

# ── Backend A: original 9-class ───────────────────────────────────────────────
SER_EMOTION_CLASSES = [
    "angry", "disgusted", "fearful", "happy",
    "neutral", "other", "sad", "surprised", "unknown",
]
# Canonical 4-zone lookup — single source of truth per guide.md Phase 2 & 6.
# Zone is selected by marginalising the full class distribution over this
# table (per-zone probability mass, max-mass zone wins), not by taking the
# argmax class first — see _ser_original.py::predict_zone_from_audio.
# "<unk>" confirmed present (empirically, near-zero probability mass) in
# emotion2vec_plus_seed's raw output alongside "unknown" — both map the same
# way. _ser_original.py's zone_mass.get(cls, "NEUTRAL_BASELINE") already
# handled this gracefully before it was added explicitly here; listed now so
# the full observed label set is documented rather than relying on the
# fallback silently.
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
    "<unk>":     "NEUTRAL_BASELINE",
}

# ── Remote SER inference (fallback for Streamlit Community Cloud) ────────────
# The primary path (this file's SER_MODEL_ID/SER_BACKEND above) runs funasr
# in-process everywhere, including on Streamlit Community Cloud, using the
# smaller "seed" backbone specifically so it fits the free tier's RAM budget.
# If that still proves too heavy in practice, SER_REMOTE_URL is a documented
# fallback: it routes inference to an identical copy of engine/ser_engine.py
# running as a small FastAPI service elsewhere (see server/) instead of
# importing funasr locally. Unset (the default) means fully in-process, both
# locally and on cloud. See server/README.md to deploy the fallback service.
# Default timeout is generous (not just inference latency): server/main.py
# warms up its default backend at startup, but switching backends via the
# ?debug=1 selector triggers a fresh cold model load server-side (measured
# ~30-60s locally) on the next request.
SER_REMOTE_URL     = os.getenv("SER_REMOTE_URL", "")
SER_REMOTE_TOKEN   = os.getenv("SER_REMOTE_TOKEN", "")
SER_REMOTE_TIMEOUT_S = float(os.getenv("SER_REMOTE_TIMEOUT_S", "90"))

# ── Backend B: CREMA-D 4-class linear probe ───────────────────────────────────
# Probe files are resolved relative to app/ in _ser_crema.py (not configurable
# here to avoid path-dependency drift; change _APP_DIR in _ser_crema.py if needed).
# Label names match linear_probe_config.json.
CREMA_LABEL_NAMES: list[str] = ["anger", "happy", "sad_fearful", "neutral"]
# CREMA probe zone strings → system canonical zone names
CREMA_PROBE_ZONE_TO_SYSTEM: dict[str, str] = {
    "pos_active":   "Q1_POS_ACT",
    "neg_active":   "Q2_NEG_ACT",
    "neg_deactive": "Q3_NEG_DEACT",
    "neutral":      "NEUTRAL_BASELINE",
}
# Documentation-only: CREMA_LABEL_NAMES[i] → system zone, mirroring the
# index→zone mapping _ser_crema.py's _PROBE_ZONE_TO_SYSTEM applies internally.
# Not imported by _ser_crema.py itself (kept private there); used by the
# methodology page for the class→zone table shown to reviewers.
CREMA_CLASS_TO_ZONE: dict[str, str] = {
    "anger":       "Q2_NEG_ACT",
    "happy":       "Q1_POS_ACT",
    "sad_fearful": "Q3_NEG_DEACT",
    "neutral":     "NEUTRAL_BASELINE",
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

# ── Recommendation blocklist ──────────────────────────────────────────────────
# Foods with known incorrect nutrient data in the current DB that should be
# temporarily excluded from all recommendations.
# Matching is exact and case-insensitive against the food's name field.
# Remove an entry once its underlying ETL data has been corrected.
# Known issues:
#   Butter    — omega3_mg loaded as 9 200 mg/100 g (correct value ≈ 330 mg)
#   Mayonnaise— omega3_mg loaded as 6 000 mg/100 g (correct value ≈ 500 mg)
#   Margarine — omega3_mg loaded as 4 000 mg/100 g (correct value ≈ 300 mg)
# These inflated values cause them to dominate Q3_NEG_DEACT / NEUTRAL_BASELINE
# primary pools until the omega3 ETL fix (moodmeal_exp pipeline) is applied.
RECOMMENDATION_BLOCKLIST: list[str] = [
    "Butter",
    "Mayonnaise",
    "Margarine",
]

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
    "EmoEating provides general meal suggestions based on mood and nutritional patterns. "
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

# ── Gemini Live voice check-in ────────────────────────────────────────────────
# Replaces the RAVDESS voice-read protocol with a short naturalistic conversation.
# The live conversation (mic capture, Gemini Live WebSocket, agent-voice gate) runs
# entirely client-side in a custom Streamlit component; the collected user-only
# audio is classified once at the end via the existing predict_zone_from_audio().
# Ephemeral token minting (server-side, real key never reaches the browser) is the
# only piece of this feature that needs Python — see services/gemini_voice.py.
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
GEMINI_LIVE_MODEL = os.getenv("GEMINI_LIVE_MODEL", "gemini-3.1-flash-live-preview")
GEMINI_VOICE      = os.getenv("GEMINI_VOICE", "Aoede")
GEMINI_WS_URL = os.getenv(
    "GEMINI_WS_URL",
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContentConstrained",
)
GEMINI_AUTH_TOKENS_URL = "https://generativelanguage.googleapis.com/v1alpha/auth_tokens"

# Conversation termination tuning — end (agent wraps up, then finalize) when EITHER
# threshold is hit, or the user clicks "Wrap up" manually. VOICE_TIMEOUT_S is the
# total-conversation (agent + user) wall-clock budget; the wrap-up goodbye plays
# INSIDE it (trigger 50s + ≤8s WRAP_UP_MAX_WAIT_MS grace ⇒ ≤58s, under the 60s cap).
VOICE_TARGET_SPEECH_S = 30.0   # seconds of detected user speech to collect
VOICE_TIMEOUT_S       = 50.0   # hard wall-clock cap on the full conversation
