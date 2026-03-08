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

## Step 3: ⚡ (Optional) Enable Optimizations

For **5-10x faster processing**:
```powershell
cp .env.optimized .env
```

This enables:
- ✅ Optimized preprocessing (256x256)
- ✅ Parallel processing (4 workers)
- ✅ Batched execution

**Skip this if you want maximum quality over speed.**

## Step 4: Start Service
```powershell
uvicorn api.main:app --host 0.0.0.0 --port 8004 --reload
```
Wait for: `INFO: All models warm. image-service is ready.`

**GPU Auto-Detection:** Service automatically detects and uses:
- 🪟 **Windows/Linux:** CUDA (NVIDIA GPUs)
- 🍎 **macOS:** MPS (Apple Silicon)
- 💻 **Fallback:** CPU

## Step 5: Run Analysis
```powershell
# Process all images
Invoke-RestMethod -Uri "http://localhost:8004/run" -Method POST

# Or test with 3 images first
Invoke-RestMethod -Uri "http://localhost:8004/run?max_images=3" -Method POST
```

## Step 6: View Results
MongoDB: `dellinnovate.image_analysis_results`
```javascript
use('dellinnovate');
db.image_analysis_results.find({});
```

---

## 🔥 That's It!

**Files Updated:**
- ✅ MongoDB storage adapter created
- ✅ PyTorch 2.8.0 with GPU support
- ✅ All dependencies updated
- ✅ Configuration files set
- ✅ GPU auto-detection enabled
- ✅ Performance optimizations available

**No manual edits needed - everything is ready to run!**

---

## 📚 Additional Resources

- **⚡ Performance Optimization** (5-10x speedup): [PERFORMANCE_OPTIMIZATION.md](PERFORMANCE_OPTIMIZATION.md)
- **🎮 GPU Detection**: [GPU_DETECTION.md](GPU_DETECTION.md)
- **📖 Full Documentation**: [README.md](README.md)
- **🧪 Benchmark Tool**: Run `bash benchmark.sh 10` to test performance
