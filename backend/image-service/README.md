# image-service

A standalone microservice that performs **OCR → sentiment analysis** and **facial emotion detection** on Instagram post images, built with **FastAPI** and **hexagonal (ports-and-adapters) architecture**.

---

## Architecture

```
image-service/
├── domain/               # Pure Python entities — no framework deps
│   └── entities.py       # ImageJob, ImageRecord, OcrResult, EmotionResult …
├── ports/                # Abstract interfaces (Python ABCs)
│   ├── ocr_port.py
│   ├── sentiment_port.py
│   ├── emotion_port.py
│   ├── preprocessing_port.py
│   └── storage_port.py
├── adapters/             # Concrete port implementations
│   ├── ocr_adapter.py          # EasyOCR
│   ├── sentiment_adapter.py    # cardiffnlp/twitter-roberta-base-sentiment-latest
│   ├── emotion_adapter.py      # dima806/facial_emotions_image_detection
│   ├── preprocessing_adapter.py# Pillow + OpenCV
│   └── storage_adapter.py      # CSV writer
├── application/          # Use-cases — orchestrate ports, zero infra deps
│   ├── filename_parser.py
│   └── use_cases.py      # ProcessSingleImage, RunBatchProcessing
├── api/                  # FastAPI entry-points
│   ├── main.py           # App factory, lifespan (warm model loading)
│   └── routes.py         # POST /run  GET /health  GET /outputs
├── config/
│   └── settings.py       # Pydantic-settings — reads .env
├── tests/
│   ├── test_filename_parsing.py
│   ├── test_csv_writing.py
│   └── test_error_handling.py
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── pyproject.toml
```

---

## Input filename convention

Images placed under `data/post_images/` must follow:

```
<ig_handle>__<YYYYMMDD>__<index>.(jpg|jpeg|png|webp)
```

Examples:
- `johndoe__20240101__0.jpg`
- `brand_co__20231215__3.png`

Files that do not match are **skipped** (never crash).

---

## Output files

| File | Description |
|---|---|
| `outputs/ocr_sentiment_results.csv` | `image_path, ig_handle, post_date, image_index, ocr_text_raw, ocr_text_clean, sentiment_label, sentiment_score, ocr_char_count, ocr_word_count, ocr_detected_bool, processed_at` |
| `outputs/face_emotion_results.csv` | `image_path, ig_handle, post_date, image_index, face_detected_bool, emotion_label, emotion_score, model_name, processed_at` |

---

## Pipelines

**Pipeline A — OCR → Sentiment**
1. EXIF auto-orient + RGB conversion
2. Optional proportional downscale (`MAX_IMAGE_SIDE_PX`)
3. Denoise (`fastNlMeansDenoisingColored`) + CLAHE contrast normalisation
4. EasyOCR text extraction
5. If `char_count >= OCR_MIN_CHARS`: HuggingFace sentiment inference

**Pipeline B — Face → Emotion**
1. EXIF auto-orient + RGB conversion
2. OpenCV Haar cascade face detection → crop largest face (10 % padding)
3. HuggingFace feature extractor + `dima806/facial_emotions_image_detection`

Both pipelines run **independently** per image — one failing never stops the other.

---

## Quick start

### Local (virtualenv)

```bash
cd backend/image-service

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Copy env template
cp .env.example .env

# Put some test images in:
mkdir -p data/post_images
cp /path/to/user__20240101__0.jpg data/post_images/

# Start the server
python -m uvicorn api.main:app --host 0.0.0.0 --port 8004 --reload
```

### Docker

```bash
cd backend/image-service
docker-compose up --build
```

**Note:** Port changed to **8004** (previously 8002)

---

## 🚀 GPU Acceleration

The service **automatically detects** the best available hardware accelerator:

| OS | Device | Speedup |
|---|---|---|
| Windows/Linux | CUDA (NVIDIA) | 6-10x faster |
| macOS | MPS (Apple Silicon) | 5-8x faster |
| Fallback | CPU | baseline |

### Quick Test

```bash
# Check what device will be used
python test_device_detection.py

# Or via API (after starting server)
curl http://localhost:8004/device
```

### Manual Override

```bash
# Force specific device
export DEVICE=cuda  # or mps, or cpu
uvicorn api.main:app --host 0.0.0.0 --port 8004 --reload
```

📚 **Full documentation:** [GPU_DETECTION.md](GPU_DETECTION.md)

---

## ⚡ Performance Optimization

**Problem: Processing taking too long?** (e.g., 7 minutes for a batch)

**Solution: Enable optimizations** for 5-10x speedup!

### Quick Fix

Copy the optimized config:
```bash
cp .env.optimized .env
# Then restart the service
```

Or add to your `.env`:
```env
USE_OPTIMIZED_PREPROCESSING=true
OPTIMIZED_TARGET_SIZE=256
PROCESSING_MODE=batched
PARALLEL_WORKERS=4
```

**Expected result:** 7 minutes → 60-90 seconds 🚀

### Features

- ✅ **Aggressive resizing** (256x256) - 2-3x faster
- ✅ **Parallel processing** - 3-4x faster
- ✅ **GPU acceleration** - 2x faster
- ✅ **Combined effect** - 5-10x faster overall

📚 **Full guide:** [PERFORMANCE_OPTIMIZATION.md](PERFORMANCE_OPTIMIZATION.md)

---

## API

### `GET /health`

```json
{"status": "healthy", "service": "image-service", "version": "1.0.0"}
```

### `GET /device`

Returns device information for debugging GPU acceleration:

```json
{
  "os": "Darwin",
  "torch_available": true,
  "cuda_available": false,
  "mps_available": true,
  "selected_device": "mps"
}
```

### `POST /run`

```json
// Request body (all optional)
{
  "input_folder": "data/post_images",
  "overwrite": true,
  "max_images": 50
}
```

```json
// Response
{
  "status": "ok",
  "total_images": 12,
  "ocr_detections": 8,
  "sentiment_inferences": 8,
  "face_detections": 5,
  "ocr_failures": 0,
  "emotion_failures": 0,
  "ocr_sentiment_output": "outputs/ocr_sentiment_results.csv",
  "face_emotion_output": "outputs/face_emotion_results.csv",
  "elapsed_seconds": 42.3
}
```

### `GET /outputs`

Lists all files in the `outputs/` folder.

---

## Configuration reference (`.env`)

| Variable | Default | Description |
|---|---|---|
| `INPUT_FOLDER` | `data/post_images` | Recursive image scan root |
| `OUTPUT_FOLDER` | `outputs` | Where CSVs are written |
| `SENTIMENT_MODEL` | `cardiffnlp/twitter-roberta-base-sentiment-latest` | HF model hub ID |
| `EMOTION_MODEL` | `dima806/facial_emotions_image_detection` | HF model hub ID |
| `DEVICE` | *auto-detect* | `cpu` / `cuda` / `mps` (auto-detected by default) |
| `OCR_LANGUAGE` | `en` | EasyOCR language code |
| `OCR_MIN_CHARS` | `10` | Min chars for sentiment to run |
| `MAX_IMAGE_SIDE_PX` | `1024` | Resize threshold before OCR (0=off) |
| `SENTIMENT_CONFIDENCE_THRESHOLD` | `0.0` | Min confidence to keep prediction |
| `MAX_IMAGES` | `0` | Cap for dev runs (0=no cap) |
| `LOG_LEVEL` | `INFO` | Python logging level |

---

## Tests

```bash
cd backend/image-service
pytest -v
```

Tests are fully isolated — no ML models loaded, no network required.
