# EmoEating

Emotion-based meal recommendation web app. A user's emotional state — chosen manually or detected from voice via Speech Emotion Recognition (SER) — is mapped onto an affect/zone model, converted into a nutritional need vector, and used to score and rank meals from a MySQL food database. Built with Streamlit.

## Tech stack

| Area | Tech |
|------|------|
| UI | Streamlit (multipage wizard) |
| Data | MySQL via SQLAlchemy + PyMySQL |
| Compute | pandas, numpy |
| Charts | Plotly |
| Fuzzy matching | rapidfuzz |
| Voice SER | funasr / modelscope (local), Google Gemini Live (cloud) |
| External APIs | Google Places / Foursquare / HERE / OSM (restaurants), IP-geo / Nominatim (geocoding) |
| Config | python-dotenv |

## Running it

```bash
pip install -r requirements.txt          # SER extras (funasr, modelscope) install separately
cp .env.example .env                     # fill in DB creds + API keys

mysql -u root -p moodmeal    < data/sql/01_schema.sql
mysql -u root -p moodmeal    < data/sql/02_seed_categories.sql
# optional Vietnamese schema:
mysql -u root -p moodmeal_vn < data/sql/vn_01_schema.sql
mysql -u root -p moodmeal_vn < data/sql/vn_02_seed_categories.sql

python etl/run_etl.py --datasets usda foodcom epicurious indian off   # see --help for options
streamlit run app/main.py
```

Env vars live in `.env` (keys prefixed `MOODMEAL_` — legacy naming, kept to match the existing database; see `.env.example`). `USE_VN_DATA=true` switches the app to the Vietnamese schema (`moodmeal_vn`). Voice-component dev harness: `streamlit run scripts/dev_voice_component_harness.py`.

## Directory structure

| Path | Purpose |
|------|---------|
| `app/main.py` | Streamlit entry point; page router (`st.navigation`) |
| `app/config.py` | Central config: emotion coordinates, zones, ENMS scoring weights, RDA references, DB env vars, disclaimer text |
| `app/pages/` | Wizard pages, in order: `01_home` → `02_profile` → `03_emotion` → `04_recommendations` → `05_methodology` |
| `app/engine/` | Recommendation + SER pipeline (see below) |
| `app/services/` | External integrations: `gemini_voice`, `food_images`, `image_cache`, `food_name_normalizer`, `location`, `restaurant_finder` |
| `app/components/` | UI widgets: `emotion_selector`, `circumplex_plot`, `meal_card`, `nutrient_bars`, `profile_form`, `food_image_gallery`, `skeleton_loader`, `restaurant_panel`, `voice_conversation/` |
| `app/db/` | `connection.py` (SQLAlchemy engine, picks schema via `USE_VN_DATA`), `queries.py` (typed SQL), `session_logger.py` |
| `app/models/` | Trained SER linear-probe weights (`best_linear_probe.pt`) + config |
| `app/utils/` | `formatting.py`, `validation.py` helpers |
| `etl/` | Data ingestion pipeline (see below) |
| `data/sql/` | Schema + seed + migration SQL (main `moodmeal`, Vietnamese `moodmeal_vn`) |
| `data/raw/` | Source datasets (USDA, Food.com, Epicurious, Indian, OpenFoodFacts, Vietnamese) |
| `data/cache/food_images.db` | SQLite cache for fetched food image URLs |
| `validation/` | SER benchmark + zone-agreement analysis scripts |
| `tests/` | Unit tests + manual CLI tools |
| `scripts/` | One-off maintenance / enrichment / debug utilities |

## Recommendation pipeline

Emotion (manual or SER) → **Physiological** → **Zone** → **NeedVector** → **Scoring** → **Ranking**.

| Stage | What it does | File |
|-------|--------------|------|
| Physiological | User profile → BMI, BMR, TDEE, per-meal kcal target | `app/engine/physiological.py` |
| Affect mapping | Emotion label → (valence, arousal) | `app/engine/affect_mapper.py` |
| Zone classification | (V, A) → one of 4 zones (Russell circumplex) | `app/engine/zone_classifier.py` |
| Need vector | Zone + meal kcal → target macros/micros | `app/engine/need_vector.py` |
| Portion | Per-food portion size defaults/adjustment | `app/engine/portion.py` |
| Scoring | ENMS 3-component score: macro + micro + preference | `app/engine/food_scorer.py` |
| Orchestration | Fetch candidates → score → dedupe → rank top-k | `app/engine/recommender.py` |

Zone definitions, macro ratios/weights, and micronutrient priorities per zone all live in `app/config.py`.

## SER voice pipeline (two backends)

| Backend | Description | Files |
|---------|-------------|-------|
| Local SER | Audio → emotion2vec embedding → zone, via one of two swappable classifiers | `app/engine/ser_engine.py` (router), `app/engine/_ser_original.py` (9-class), `app/engine/_ser_crema.py` (CREMA-D 4-class linear probe), `app/models/` |
| Gemini Live | Cloud voice conversation; mints ephemeral tokens server-side, audio classified via the same local SER on completion | `app/services/gemini_voice.py`, `app/components/voice_conversation/` |

Active backend is selected by `SER_BACKEND` in `app/config.py`. Both paths funnel into the same zone → need-vector → scoring chain.

## ETL pipeline

`etl/run_etl.py` orchestrates loaders and transformers into the MySQL schema.

| Component | Files |
|-----------|-------|
| Config | `etl/config.py` |
| Loaders (one per source) | `etl/loaders/load_usda.py`, `load_foodcom.py`, `load_epicurious.py`, `load_indian.py`, `load_openfoodfacts.py`, `load_vietnamese.py` |
| Transformers | `etl/transformers/recipe_parser.py`, `tag_classifier.py`, `nutrient_normalizer.py`, `bmi_calculator.py` |

## Database schema

`data/sql/` — `01_schema.sql` + `02_seed_categories.sql` (main `moodmeal` schema); `vn_*.sql` (Vietnamese `moodmeal_vn` schema, same structure); numbered migrations for vitamins, normalization cache, user-study self-report columns, and restaurant-source enum.

## Testing & validation

- Unit tests (`pytest`): `tests/test_affect_mapper.py`, `test_food_scorer.py`, `test_need_vector.py`, `test_physiological.py`, `test_location.py`, `test_restaurant_finder.py`, `test_gemini_voice.py`, `test_voice_panel_contract.py`
- Manual CLI tool: `tests/test_map.py` (exercises restaurant search across providers)
- Analysis scripts: `validation/ravdess_benchmark.py` (SER accuracy vs. RAVDESS), `validation/zone_agreement.py` (detected zone vs. self-reported zone agreement)

## Where to look for X

| I want to… | Go to |
|------------|-------|
| Change scoring weights (ENMS blend) | `app/config.py` (`ENMS_MACRO_ALPHA`, `ENMS_MICRO_BETA`) |
| Add / edit an emotion | `app/config.py` (`EMOTION_COORDS`) |
| Change zone definitions or thresholds | `app/config.py` (`ZONE_LABELS`, `THETA_NEUTRAL`) + `app/engine/zone_classifier.py` |
| Tune per-zone macro/micro targets | `app/config.py` (`ZONE_MACRO_RATIOS`, `ZONE_MACRO_WEIGHTS`, `ZONE_MICRONUTRIENT_PRIORITIES`) |
| Change ranking / dedupe logic | `app/engine/recommender.py` |
| Add a new food data source | `etl/loaders/` (new loader) + register in `etl/run_etl.py` |
| Adjust DB connection / schema switch | `app/config.py`, `app/db/connection.py`, `.env` |
| Swap or tune the SER backend | `app/config.py` (`SER_BACKEND`), `app/engine/ser_engine.py` |
| Edit a wizard page | `app/pages/0X_*.py` |
| Change the disclaimer text | `app/config.py` (`UI_DISCLAIMER`) |
| Fix food image fetching | `app/services/food_images.py`, `app/services/image_cache.py`, `app/services/food_name_normalizer.py` |
| Change restaurant search / ranking | `app/services/restaurant_finder.py`, `app/services/location.py` |
