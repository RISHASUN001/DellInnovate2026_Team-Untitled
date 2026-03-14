# ============================================================
# image-service — multi-stage Dockerfile
# ============================================================
#
# Stage 1: builder — install dependencies into a virtual-env
# Stage 2: runtime — copy only what is needed, run as non-root
# ============================================================

# ---- Stage 1: builder --------------------------------------------------
FROM python:3.11-slim AS builder

# System deps needed to compile/install packages
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender-dev \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy only requirements first so Docker layer-cache is reused on code changes
COPY requirements.txt .

RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


# ---- Stage 2: runtime --------------------------------------------------
FROM python:3.11-slim AS runtime

# Runtime system libs (OpenCV, EasyOCR shared libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual-env from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user
RUN useradd -m -u 1001 appuser

WORKDIR /app

# Copy application source
COPY --chown=appuser:appuser . .

# Create expected directories
RUN mkdir -p data/post_images outputs && chown -R appuser:appuser data outputs

USER appuser

# Set PYTHONPATH so absolute imports work from the service root
ENV PYTHONPATH="/app"

EXPOSE 8002

# Docker HEALTHCHECK — calls the /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/health')" \
    || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "1"]
