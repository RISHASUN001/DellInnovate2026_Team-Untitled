# Image Service - Complete Setup Guide

## Prerequisites
- Python 3.11 or higher
- NVIDIA GPU with CUDA support (for GPU acceleration)
- CUDA Toolkit 12.1 or higher
- Git

---

## 1. Initial Setup

### Clone the repository (if not already done)
```powershell
cd C:\Users\janha\Desktop\DellInnovate2026_Team-Untitled\backend\image-service
```

### Create and activate virtual environment
```powershell
# Create virtual environment
python -m venv .venv

# Activate it
.\.venv\Scripts\Activate.ps1
```

---

## 2. Install CUDA-enabled PyTorch

**CRITICAL: Install PyTorch with CUDA support FIRST before other dependencies**

```powershell
# Upgrade pip first
pip install --upgrade pip

# Install PyTorch with CUDA 12.1 support
pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu121
```

**Verify CUDA is working:**
```powershell
python -c "import torch; print('CUDA available:', torch.cuda.is_available()); print('CUDA device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"
```

You should see:
```
CUDA available: True
CUDA device: NVIDIA GeForce RTX 3050 Laptop GPU
```

---

## 3. Install All Dependencies

```powershell
pip install -r requirements.txt
```

This will install:
- FastAPI and Uvicorn (web framework)
- Transformers and Accelerate (for AI models)
- PyMongo (MongoDB driver)
- Pillow and OpenCV (image processing)
- All other dependencies

---

## 4. Verify Installation

Check all critical packages:
```powershell
python -c "import torch, transformers, pymongo, fastapi; print('torch:', torch.__version__); print('transformers:', transformers.__version__); print('pymongo:', pymongo.__version__); print('fastapi:', fastapi.__version__)"
```

Expected output:
```
torch: 2.6.0+cu121
transformers: 4.45.0
pymongo: 4.6.0
fastapi: 0.111.0
```

---

## 5. Prepare Image Input Folder

Place your Instagram post images in the correct folder:
```
backend/image-service/data/post_images/
```

**Image naming convention:**
```
{ig_handle}__{YYYYMMDD}__{index}.{ext}
```

Examples:
- `johndoe__20260226__0.png`
- `janedoe__20260301__1.jpg`

---

## 6. Configuration

Your `.env` file is already configured with:
```env
DEVICE=cuda
MONGODB_URI=mongodb+srv://rishikamehta2004:rishu2004@cluster0.1yrcnpc.mongodb.net/dellinnovate?retryWrites=true&w=majority
MONGODB_DB_NAME=dellinnovate
MONGODB_COLLECTION_NAME=image_analysis_results
LOG_LEVEL=INFO
```

---

## 7. Start the Service

```powershell
# Make sure you're in the image-service directory with activated venv
cd C:\Users\janha\Desktop\DellInnovate2026_Team-Untitled\backend\image-service

# Start the server
uvicorn api.main:app --host 0.0.0.0 --port 8002
```

**Wait for models to load (first time ~30 seconds):**
```
INFO: Loading SmolVLM model 'HuggingFaceTB/SmolVLM-Instruct' on cuda…
INFO: SmolVLM model ready.
INFO: Loading sentiment model 'cardiffnlp/twitter-roberta-base-sentiment-latest' on device_id=0…
INFO: Sentiment model ready.
INFO: Loading emotion model 'dima806/facial_emotions_image_detection'…
INFO: Emotion model ready.
INFO: All models warm. image-service is ready.
INFO: Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:8002
```

---

## 8. Run Image Analysis

### Option A: Via API (FastAPI Docs)
1. Open browser: http://localhost:8002/docs
2. Click on `POST /run`
3. Click "Try it out"
4. Click "Execute"

### Option B: Via PowerShell
```powershell
Invoke-RestMethod -Uri "http://localhost:8002/run" -Method POST
```

### Option C: Via Python
```python
import requests
response = requests.post("http://localhost:8002/run")
print(response.json())
```

---

## 9. Check Results in MongoDB

Your analysis results will be saved to MongoDB:
- **Database:** `dellinnovate`
- **Collection:** `image_analysis_results`

Each document contains:
```json
{
  "image_path": "data/post_images/johndoe__20260226__0.png",
  "ig_handle": "johndoe",
  "post_date": "2026-02-26T00:00:00",
  "image_index": 0,
  "analysis_type": "ocr_sentiment" or "emotion",
  "ocr_data": { ... },
  "sentiment_data": { ... },
  "emotion_data": { ... },
  "vlm_analysis": { ... },
  "processed_at": "2026-03-07T12:00:00"
}
```

You can query using MongoDB Compass or mongosh:
```javascript
use('dellinnovate');
db.image_analysis_results.find({});
```

---

## 10. Troubleshooting

### CUDA Not Available
```powershell
# Reinstall PyTorch with CUDA
pip uninstall torch torchvision torchaudio -y
pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu121
```

### MongoDB Connection Failed
- Check internet connection
- Verify MongoDB Atlas cluster is running
- Check credentials in `.env` file

### Model Loading Errors
```powershell
# Clear HuggingFace cache and re-download
rm -r ~\.cache\huggingface
```

### Out of Memory (GPU)
Edit `.env` to use CPU:
```env
DEVICE=cpu
```

---

## 11. GPU Performance Monitoring

Monitor GPU usage while processing:
```powershell
# In a separate terminal
nvidia-smi -l 1
```

---

## 12. API Endpoints

- `GET /health` - Check service health
- `POST /run` - Process all images in data/post_images/
- `GET /docs` - Interactive API documentation
- `GET /openapi.json` - OpenAPI schema

---

## Summary of Key Commands

```powershell
# 1. Activate environment
.\.venv\Scripts\Activate.ps1

# 2. Install PyTorch with CUDA
pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu121

# 3. Install dependencies
pip install -r requirements.txt

# 4. Verify CUDA
python -c "import torch; print('CUDA:', torch.cuda.is_available())"

# 5. Start service
uvicorn api.main:app --host 0.0.0.0 --port 8002

# 6. Run analysis
Invoke-RestMethod -Uri "http://localhost:8002/run" -Method POST
```

---

## Next Steps

1. ✅ Place images in `data/post_images/`
2. ✅ Start the service with `uvicorn api.main:app --host 0.0.0.0 --port 8002`
3. ✅ Call `POST /run` to process images
4. ✅ Check MongoDB for results

**Your service is now fully configured to use GPU acceleration and store results in MongoDB!**
