# SER inference server

Why this exists: Streamlit Community Cloud's free tier (~1 GB RAM, minimal
base image, no `packages.txt`/system audio libs) cannot run `funasr` +
`emotion2vec_plus_large` in-process — that's the root cause of the "SER
module not installed" message that only ever showed up on the cloud
deployment, never locally. This server runs the **exact same**
`app/engine/ser_engine.py` code (unmodified) on a host that actually has the
RAM/disk/system libs to load the model, and the Streamlit app calls it over
HTTP instead of importing `funasr` directly. Same model, same code path —
only the compute location changes, which keeps SER results identical
regardless of where the app is deployed (see `app/engine/_ser_remote.py`).

## Endpoints

- `GET /health` → `{"status": "ok", "ser_available": bool}`
- `POST /predict?backend=crema4class|original` (multipart `audio` file, WAV
  bytes) → `{"zone": str, "probs": {...}, "backend": {...}}`

Both accept an optional `Authorization: Bearer <SER_SERVER_TOKEN>` header;
required only if `SER_SERVER_TOKEN` is set on the server.

## Deploy options (pick one — all need ≥2-4 GB RAM / a few GB disk)

### Render (Docker web service) — no new repo needed

This server deploys straight out of **this same repo** — Render's Docker
services support a monorepo layout where the Dockerfile lives in a
subdirectory but the build context is the repo root (needed here because
`server/Dockerfile` does `COPY app/ ...` as a sibling directory, which is
what keeps server-side inference byte-identical to local dev).

**Option A — Blueprint (recommended, committed config, no manual dashboard
guesswork):** a `render.yaml` already exists at the repo root. Render
dashboard → **New** → **Blueprint** → select this GitHub repo and the branch
you want deployed → Render reads `render.yaml` automatically. After the first
deploy, go to the service → **Environment** and set `SER_SERVER_TOKEN`
(the file intentionally leaves it out — `sync: false` — so it's never
committed).

**Option B — Manual Web Service**, if you'd rather not use a Blueprint:
1. New → **Web Service** → connect this repo → **Runtime: Docker**.
2. **Root Directory**: leave blank (repo root) — do NOT set it to `server/`,
   or changes to `app/engine/` won't trigger rebuilds.
3. **Dockerfile Path**: `server/Dockerfile`
4. **Docker Build Context Directory**: leave blank (defaults to repo root —
   exactly what the Dockerfile needs).
5. Environment → add `SER_SERVER_TOKEN` (any long random string).
6. **Instance type**: Standard (2 GB) is the minimum worth trying; Pro (4 GB)
   is the safer default — a single emotion2vec_plus_large tensor alone
   allocates ~650 MB, and torch/funasr framework overhead plus the transient
   2x memory spike during model deserialization pushed this past 1 GB in
   local testing. Render's Free/Starter tiers (512 MB) will OOM the same way
   Streamlit Community Cloud did — that's the exact failure this server
   exists to avoid, so don't use them here.
7. Health check path: `/health` (already set in `render.yaml` for Option A).
8. Deploy, then note the public URL (`https://<service-name>.onrender.com`)
   — that's your `SER_REMOTE_URL`.

Render free/low tiers also spin down on idle — if you're on one, the first
request after idle will be slow (cold container boot + the warm-up below).
A paid always-on instance avoids that; worth it before a live study session.

### Hugging Face Spaces (Docker SDK) — needs a paid tier for Docker
1. Create a new Space → SDK: **Docker**.
2. Push this repo's contents (or just `server/` + `app/`) to the Space repo,
   with `server/Dockerfile` at the path HF expects (`Dockerfile` at repo
   root of the Space, or set the Space's Dockerfile path to `server/Dockerfile`
   with build context = repo root).
3. Space → Settings → Repository secrets: add `SER_SERVER_TOKEN` (pick any
   long random string).
4. Space boots `uvicorn` on port 7860 by default for HF — if using HF's
   Docker SDK, override with `EXPOSE 7860` and `--port 7860`, or set the
   Space's "App port" to 8000 in settings (adjust to match).
5. Your endpoint is `https://<your-space>.hf.space`.

### Any VM (manual)
```bash
docker build -f server/Dockerfile -t emoeating-ser-server .
docker run -d -p 8000:8000 -e SER_SERVER_TOKEN=your_long_random_secret emoeating-ser-server
```

## Wire it into the Streamlit app

In the Streamlit Cloud app's **Secrets** (or `.env` for any other remote
host), set:

```
SER_REMOTE_URL=https://your-deployed-server
SER_REMOTE_TOKEN=your_long_random_secret   # must match SER_SERVER_TOKEN above
```

Leave both unset for local dev — the app then keeps using `funasr` in-process
exactly as before. See `.env.example`.

## Verifying it works

```bash
curl https://your-deployed-server/health
curl -X POST "https://your-deployed-server/predict?backend=crema4class" \
     -H "Authorization: Bearer your_long_random_secret" \
     -F "audio=@some_test_clip.wav"
```

Then reload the app's Emotion page — voice check-in should classify without
showing any SER warning.
