# syntax=docker/dockerfile:1

# Lyrics alignment service: Demucs stem separation + WhisperX alignment.
#
# TORCH_VARIANT selects the PyTorch wheel index:
#   cpu   -> CPU-only image (default, works everywhere)
#   cu128 -> CUDA 12.8 wheels; run with the NVIDIA Container Toolkit
#            (see compose.gpu.yaml)
FROM python:3.11-slim-bookworm

ARG TORCH_VARIANT=cpu
ARG TORCH_VERSION=2.8.0
ARG TORCHAUDIO_VERSION=2.8.0
ARG TORCHVISION_VERSION=0.23.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Model caches live on a named volume so weights download only once.
    HF_HOME=/models/huggingface \
    TORCH_HOME=/models/torch \
    NLTK_DATA=/models/nltk \
    XDG_CACHE_HOME=/models/cache \
    # ctranslate2 (faster-whisper) loads cuDNN/cuBLAS dynamically; point it at
    # the libraries shipped with the CUDA PyTorch wheels. Harmless on CPU.
    LD_LIBRARY_PATH=/usr/local/lib/python3.11/site-packages/nvidia/cudnn/lib:/usr/local/lib/python3.11/site-packages/nvidia/cublas/lib

# ffmpeg is required by Demucs, WhisperX audio loading, and torchcodec.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install PyTorch first from the selected index, then pin it as a constraint
# so the remaining requirements cannot replace it with a different build.
RUN pip install \
        --index-url "https://download.pytorch.org/whl/${TORCH_VARIANT}" \
        "torch==${TORCH_VERSION}" \
        "torchaudio==${TORCHAUDIO_VERSION}" \
        "torchvision==${TORCHVISION_VERSION}" \
    && pip freeze | grep -E '^(torch|torchaudio|torchvision)==' > /tmp/torch-constraints.txt

COPY requirements.txt .
RUN pip install -c /tmp/torch-constraints.txt -r requirements.txt

RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/runtime /models \
    && chown -R app:app /app /models

COPY --chown=app:app src ./src

USER app

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=4)"

# A single worker: jobs are tracked in memory and the pipeline is serialized
# by an in-process semaphore to keep GPU memory usage bounded.
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
