# EmoEating SER inference server.
# Build from the REPO ROOT (needs both server/ and app/):
#   docker build -f server/Dockerfile -t emoeating-ser-server .
# Run:
#   docker run -p 8000:8000 -e SER_SERVER_TOKEN=... emoeating-ser-server

FROM python:3.11-slim

# libsndfile1/ffmpeg: audio decode libraries funasr's torchaudio/soundfile
# backends need at import/runtime — absent on minimal base images, which is
# what breaks `import funasr` on platforms without an apt step (e.g. the
# original Streamlit Community Cloud failure this server exists to avoid).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

# CPU-only torch/torchaudio FIRST, from PyTorch's dedicated CPU wheel index,
# in its own isolated pip command. This is deliberate, not cosmetic: pip
# prefers PyPI's default (CUDA-bundled) build over the +cpu-tagged build
# whenever both indexes are visible in the same resolution pass — even with
# --extra-index-url — because PEP 440 ranks an unsuffixed local version
# above a "+cpu" one. Running this as a standalone command with only the CPU
# index visible sidesteps that entirely. This alone cuts the image by several
# GB (unused CUDA/cuDNN/NCCL libs) since this server only ever runs on CPU.
# torchaudio is explicit, not incidental: funasr.utils.load_utils imports it
# unconditionally despite funasr's own packaging not declaring it as a hard
# dependency — confirmed by a clean-venv test where omitting it broke
# `import funasr` entirely. torchvision is NOT needed by this audio-only
# pipeline and is deliberately omitted.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch torchaudio

COPY server/requirements.txt /srv/server/requirements.txt
RUN pip install --no-cache-dir -r /srv/server/requirements.txt

COPY app/ /srv/app/
COPY server/main.py /srv/server/main.py

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# --app-dir explicitly puts /srv on sys.path so `server.main` resolves as a
# namespace package regardless of how the container's WORKDIR is invoked.
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "/srv"]
