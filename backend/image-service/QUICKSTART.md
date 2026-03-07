# 🚀 Quick Start - Image Service

## Step 1: Setup (One-time)
```powershell
cd C:\Users\janha\Desktop\DellInnovate2026_Team-Untitled\backend\image-service
.\.venv\Scripts\Activate.ps1
.\setup.ps1
```

## Step 2: Add Images
Place images in: `data\post_images\`
Format: `{handle}__{YYYYMMDD}__{index}.{ext}`
Example: `johndoe__20260226__0.png`

## Step 3: Start Service
```powershell
uvicorn api.main:app --host 0.0.0.0 --port 8002
```
Wait for: `INFO: All models warm. image-service is ready.`

## Step 4: Run Analysis
```powershell
Invoke-RestMethod -Uri "http://localhost:8002/run" -Method POST
```

## Step 5: View Results
MongoDB: `dellinnovate.image_analysis_results`
```javascript
use('dellinnovate');
db.image_analysis_results.find({});
```

---

## 🔥 That's It!

**Files Updated:**
- ✅ MongoDB storage adapter created
- ✅ PyTorch 2.6.0 with CUDA
- ✅ All dependencies updated
- ✅ Configuration files set

**No manual edits needed - everything is ready to run!**
