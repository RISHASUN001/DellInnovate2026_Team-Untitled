#!/usr/bin/env bash
# =============================================================
# setup.sh — one-shot setup for image-service
#
# Usage:
#   chmod +x setup.sh
#   ./setup.sh
#
# What it does:
#   1. Checks Python 3.11+
#   2. Creates .venv if it doesn't exist
#   3. Installs all Python dependencies
#   4. Creates data/post_images/ and outputs/ directories
#   5. Copies .env.example → .env if .env doesn't exist
#   6. Pre-downloads the HuggingFace models so the first run
#      doesn't time out waiting for downloads
# =============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ----- helpers -------------------------------------------------------
green()  { echo -e "\033[32m$*\033[0m"; }
yellow() { echo -e "\033[33m$*\033[0m"; }
red()    { echo -e "\033[31m$*\033[0m"; }
bold()   { echo -e "\033[1m$*\033[0m"; }

bold "========================================="
bold " image-service  setup"
bold "========================================="

# ----- 1. Python version check ---------------------------------------
PYTHON=$(command -v python3 || true)
if [ -z "$PYTHON" ]; then
  red "python3 not found. Install Python 3.11+ and re-run."
  exit 1
fi

PY_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$("$PYTHON" -c "import sys; print(sys.version_info.major)")
PY_MINOR=$("$PYTHON" -c "import sys; print(sys.version_info.minor)")

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
  red "Python 3.10+ required (found $PY_VER). Please upgrade."
  exit 1
fi
green "✓ Python $PY_VER found at $PYTHON"

# ----- 2. Virtual environment ----------------------------------------
VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
  yellow "Creating virtual environment at .venv …"
  "$PYTHON" -m venv "$VENV_DIR"
  green "✓ Virtual environment created"
else
  green "✓ Virtual environment already exists"
fi

PIP="$VENV_DIR/bin/pip"
PYTHON_VENV="$VENV_DIR/bin/python"

# ----- 3. Install dependencies ----------------------------------------
yellow "Upgrading pip …"
"$PIP" install --quiet --upgrade pip

yellow "Installing dependencies from requirements.txt …"
yellow "  (This can take 5-15 minutes the first time — torch + transformers are large)"
"$PIP" install --quiet -r requirements.txt
green "✓ All Python packages installed"

# ----- 4. Directories -------------------------------------------------
mkdir -p data/post_images outputs
green "✓ data/post_images/ and outputs/ are ready"

# ----- 5. .env file ---------------------------------------------------
if [ ! -f ".env" ]; then
  cp .env.example .env
  yellow "  .env created from .env.example — edit it if needed"
else
  green "✓ .env already exists"
fi

# ----- 6. Pre-download HuggingFace models ----------------------------
yellow "Pre-downloading HuggingFace models (runs once, cached for future use) …"
yellow "  Sentiment model: cardiffnlp/twitter-roberta-base-sentiment-latest"
yellow "  Emotion model:   dima806/facial_emotions_image_detection"

"$PYTHON_VENV" - <<'PYEOF'
import sys

print("  Downloading sentiment model…", flush=True)
try:
    from transformers import pipeline
    pipe = pipeline(
        "text-classification",
        model="cardiffnlp/twitter-roberta-base-sentiment-latest",
        device=-1,
        top_k=1,
    )
    # Quick smoke-test
    pipe("hello world", truncation=True, max_length=512)
    print("  ✓ Sentiment model ready")
except Exception as e:
    print(f"  ✗ Sentiment model download failed: {e}", file=sys.stderr)
    sys.exit(1)

print("  Downloading emotion model…", flush=True)
try:
    from transformers import AutoFeatureExtractor, AutoModelForImageClassification
    AutoFeatureExtractor.from_pretrained("dima806/facial_emotions_image_detection")
    AutoModelForImageClassification.from_pretrained("dima806/facial_emotions_image_detection")
    print("  ✓ Emotion model ready")
except Exception as e:
    print(f"  ✗ Emotion model download failed: {e}", file=sys.stderr)
    sys.exit(1)

print("  Initialising EasyOCR (downloads language model on first run)…", flush=True)
try:
    import easyocr
    easyocr.Reader(["en"], gpu=False, verbose=False)
    print("  ✓ EasyOCR ready")
except Exception as e:
    print(f"  ✗ EasyOCR init failed: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF

green "✓ All models downloaded and cached"

# ----- Done -----------------------------------------------------------
bold ""
bold "========================================="
bold " Setup complete!"
bold "========================================="
echo ""
echo "  Next steps:"
echo ""
echo "  1. Put images in:  data/post_images/"
echo "     Name them like: johndoe__20240101__0.jpg"
echo ""
echo "  2. Activate the venv:"
echo "     source .venv/bin/activate"
echo ""
echo "  3. Start the server:"
echo "     uvicorn api.main:app --host 0.0.0.0 --port 8002 --reload"
echo ""
echo "  4. Trigger a run:"
echo "     curl -X POST http://localhost:8002/run"
echo ""
echo "  5. Find results in:  outputs/"
echo ""
