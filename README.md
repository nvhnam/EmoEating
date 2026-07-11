# EmoEating

Emotion-based meal recommendation web app. A user's emotional state — elicited through a live voice conversation with a Gemini agent (or chosen manually) and detected via Speech Emotion Recognition (SER) — is mapped onto an affect/zone model, converted into a nutritional need vector, and used to score and rank meals from a MySQL food database. Built with Streamlit. The Gemini Live conversational elicitation is one of this project's core research contributions, not just a UI convenience.

## Tech stack

| Area | Tech |
|------|------|
| UI | Streamlit (multipage wizard) |
| Data | MySQL via SQLAlchemy + PyMySQL |
| Compute | pandas, numpy |
| Charts | Plotly |
| Fuzzy matching | rapidfuzz |
| Voice SER | Google Gemini Live (conversational elicitation, runs client-side in the browser), funasr / modelscope (emotion2vec_plus_seed) for classification — the whole stack runs in-process everywhere, including Streamlit Community Cloud |
| External APIs | Google Places / Foursquare / HERE / OSM (restaurants), IP-geo / Nominatim (geocoding) |
| Config | python-dotenv |

## Running it

```bash
pip install -r requirements.txt          # includes funasr/modelscope/torch (CPU) for voice SER
cp .env.example .env                     # fill in DB creds + API keys

mysql -u root -p moodmeal    < data/sql/01_schema.sql
mysql -u root -p moodmeal    < data/sql/02_seed_categories.sql
# optional Vietnamese schema:
mysql -u root -p moodmeal_vn < data/sql/vn_01_schema.sql
mysql -u root -p moodmeal_vn < data/sql/vn_02_seed_categories.sql

python etl/run_etl.py --datasets usda foodcom epicurious indian off   # see --help for options
streamlit run app/main.py
```

Env vars live in `.env` (keys prefixed `MOODMEAL_` — legacy naming, kept to match the existing database; see `.env.example`). `USE_VN_DATA=true` switches the app to the Vietnamese schema (`moodmeal_vn`). `packages.txt` (ffmpeg, libsndfile1) provides the system audio libraries funasr needs — Streamlit Community Cloud reads it automatically; for any other Linux host, `apt-get install -y $(cat packages.txt)` before installing Python deps.

## Directory structure

| Path | Purpose |
|------|---------|
| `app/main.py` | Streamlit entry point; page router (`st.navigation`) |
| `app/config.py` | Central config: emotion coordinates, zones, ENMS scoring weights, RDA references, DB env vars, disclaimer text |
| `app/pages/` | Wizard pages, in order: `01_home` → `02_profile` → `03_emotion` → `04_recommendations` → `05_methodology` |
| `app/engine/` | Recommendation + SER pipeline (see below) |
| `app/services/` | External integrations: `gemini_voice` (Gemini Live ephemeral token minting — the voice check-in's server-side piece), `food_images`, `image_cache`, `food_name_normalizer`, `location`, `restaurant_finder` |
| `app/components/` | UI widgets: `emotion_selector`, `circumplex_plot`, `meal_card`, `nutrient_bars`, `profile_form`, `food_image_gallery`, `skeleton_loader`, `restaurant_panel`, `voice_conversation/` (the Gemini Live conversation custom component — mic capture, WebSocket, agent-voice gate) |
| `app/db/` | `connection.py` (SQLAlchemy engine, picks schema via `USE_VN_DATA`), `queries.py` (typed SQL), `session_logger.py` |
| `app/models/` | Trained SER linear-probe weights (`best_linear_probe.pt`) + config — currently inactive, see SER voice pipeline section |
| `app/utils/` | `formatting.py`, `validation.py` helpers |
| `server/` | Deployable FastAPI wrapper around `app/engine/ser_engine.py` — a documented fallback if in-process SER proves too heavy on your actual Streamlit Cloud quota, not needed by default. See `server/README.md` |
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

## SER voice pipeline

Two independent concerns, easy to conflate but worth keeping separate:

| Piece | Description | Files |
|-------|-------------|-------|
| Voice conversation (capture) | Live mic capture + Gemini Live WebSocket conversation, running almost entirely client-side in the browser; collects user-only audio. **A core research contribution** — the conversational elicitation itself, not just a recording mechanism. Cheap and was never the source of the cloud RAM issue: it needs one lightweight server-side ephemeral-token mint, nothing else | `app/services/gemini_voice.py` (token minting), `app/components/voice_conversation/` (the custom component) |
| SER classification | The collected audio → emotion2vec's built-in classification head → zone. This is what actually needed a multi-GB model load, and is the part that broke on Streamlit Community Cloud | `app/engine/ser_engine.py` (router), `app/engine/_ser_original.py` (the only active backend — "original" 9-class, off-the-shelf), `app/models/` |
| Remote SER (fallback) | Same classifier code, run as a FastAPI service elsewhere — used instead of in-process funasr only if `SER_REMOTE_URL` is set. Does not affect the conversation step above at all | `app/engine/_ser_remote.py` (client), `server/` (the deployable service) |

The active backbone is `iic/emotion2vec_plus_seed` (`SER_MODEL_ID` in
`app/config.py`) — sized down from the original `_large` variant (~1.0 GB vs.
~1.9 GB checkpoint) specifically so classification fits Streamlit Community
Cloud's free-tier RAM budget running in-process, alongside the (already
cloud-safe) Gemini conversation. The CREMA-D 4-class linear probe
(`_ser_crema.py`, `app/models/best_linear_probe.pt`) is **currently
disabled** (`SER_BACKEND = "original"`) — that probe was trained
specifically on `_large`'s 1024-d embeddings and is not compatible with the
smaller backbone; selecting it via the `?debug=1` panel raises a clear
error rather than silently mis-predicting (see `_ser_crema.py`'s dimension
check). Retrain a probe against the seed backbone's embedding dimension
before re-enabling it.

### Deploying to Streamlit Community Cloud

1. Set `GEMINI_API_KEY` in the app's Secrets — required for the voice
   conversation (unrelated to the RAM issue below; always worked on cloud).
2. `requirements.txt` already pins CPU-only torch + the smaller
   `emotion2vec_plus_seed` backbone, and `packages.txt` supplies the system
   audio libraries (`ffmpeg`, `libsndfile1`) Streamlit Cloud's base image
   lacks by default — both are read automatically by Streamlit Cloud's build.
3. Deploy as normal; no extra secrets are required for SER classification
   itself beyond the above.
4. **If classification still doesn't fit** your actual Streamlit Cloud RAM
   quota (this wasn't verified against a live Streamlit Cloud deploy — only
   measured locally and via a real Docker build), fall back to the separate
   inference server: deploy `server/` (see `server/README.md`), then set
   `SER_REMOTE_URL` + `SER_REMOTE_TOKEN` in the Streamlit Cloud app's
   Secrets. No code change needed either way — `ser_engine.py` routes
   in-process vs. remote purely based on whether `SER_REMOTE_URL` is set,
   and the Gemini conversation step is unaffected either way.
5. If SER classification is unavailable through either path, the Emotion
   page degrades gracefully to the manual mood picker (no dead-end
   "pip install" message shown to hosted users).

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
| Swap the SER backbone size or model | `app/config.py` (`SER_MODEL_ID`) — remember the CREMA-D probe is backbone-size-locked, see SER voice pipeline section |
| Retrain the CREMA-D probe for the current backbone | Not present in this repo — `app/models/best_linear_probe.pt` was trained externally; see `app/models/linear_probe_config.json` for the expected format |
| Deploy the SER fallback server (only if in-process SER doesn't fit your cloud RAM quota) | `server/README.md`, `app/engine/_ser_remote.py`, `SER_REMOTE_URL`/`SER_REMOTE_TOKEN` in `.env.example` |
| Tune the Gemini Live voice conversation (elicitation prompts, timing, voice) | `app/services/gemini_voice.py`, `app/components/voice_conversation/`, `VOICE_TARGET_SPEECH_S`/`VOICE_TIMEOUT_S` in `app/config.py` |
| Edit a wizard page | `app/pages/0X_*.py` |
| Change the disclaimer text | `app/config.py` (`UI_DISCLAIMER`) |
| Fix food image fetching | `app/services/food_images.py`, `app/services/image_cache.py`, `app/services/food_name_normalizer.py` |
| Change restaurant search / ranking | `app/services/restaurant_finder.py`, `app/services/location.py` |
