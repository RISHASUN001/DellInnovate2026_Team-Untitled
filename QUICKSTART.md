# 🚀 Quick Start Guide - Analytics Pipeline

This guide will help you set up and run the emotional distress detection analytics pipeline.

## Prerequisites

- Python 3.10 or higher
- MongoDB connection (local or Atlas)
- 4GB RAM minimum (8GB recommended)
- ~2GB disk space for NLP models

## Step 1: Install Dependencies

```bash
# Navigate to backend directory
cd backend

# Using Poetry (recommended)
poetry install

# Or using pip
pip install torch transformers sentence-transformers numpy fastapi motor loguru python-dotenv scrapfly-sdk
```

## Step 2: Configure Environment

Create `.env` file in the root directory:

```env
# MongoDB Configuration
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/database
MONGODB_DB_NAME=instagram_scraper

# Collection Names (optional, these are defaults)
MONGODB_COLLECTION_USERS=instagram_users
MONGODB_COLLECTION_POSTS=instagram_posts
MONGODB_COLLECTION_SCRAPES=scrape_jobs

# Scrapfly API (for Instagram scraping)
SCRAPFLY_KEY=your_scrapfly_key_here
```

## Step 3: Test MongoDB Connection

Run the existing `dbtest.ipynb` notebook or use:

```python
from config.database import MongoDB

async def test():
    await MongoDB.connect_db()
    db = MongoDB.get_db()
    count = await db.instagram_posts.count_documents({})
    print(f"✅ Connected! Found {count} posts")

await test()
```

## Step 4: Download NLP Models (First Run)

Models will download automatically on first use (~2GB):

```python
from analytics.nlp_models import NLPPipeline

# This will download all 3 models
pipeline = NLPPipeline()
print("✅ All models loaded!")
```

Expect 5-10 minutes for first download depending on internet speed.

## Step 5: Run the Pipeline

### Option A: Using Jupyter Notebook (Recommended)

```bash
jupyter notebook analytics_demo.ipynb
```

Follow the step-by-step cells in the notebook.

### Option B: Using Python Script

```python
import asyncio
from config.database import MongoDB
from analytics.signal_extraction import run_nlp_extraction
from analytics.feature_engineering import run_feature_engineering

async def main():
    # Connect to database
    await MongoDB.connect_db()
    
    # Stage 1: Extract NLP signals
    print("🚀 Running Stage 1: NLP Signal Extraction...")
    stage1 = await run_nlp_extraction(limit=10)  # Start with 10 posts
    print(f"✅ Stage 1 complete: {stage1['signals_created']} signals created")
    
    # Stage 2: Compute risk profiles  
    print("🚀 Running Stage 2: Feature Engineering...")
    stage2 = await run_feature_engineering(window_days=7)
    print(f"✅ Stage 2 complete: {stage2['profiles_created']} profiles created")
    
    # Close database
    await MongoDB.close_db()

# Run it
asyncio.run(main())
```

### Option C: Using REST API

```bash
# Start the server
cd backend
uvicorn app:app --reload --port 8000

# In another terminal, run the pipeline
curl -X POST http://localhost:8000/api/analytics/run-full-pipeline \
  -H "Content-Type: application/json" \
  -d '{"limit_posts": 10, "window_days": 7}'
```

## Step 6: View Results

### Check Database Collections

```python
from pymongo import MongoClient
from config.database import MongoDB

async def view_results():
    await MongoDB.connect_db()
    db = MongoDB.get_db()
    
    # Count signals
    signals_count = await db.text_units_signals.count_documents({})
    print(f"📊 NLP Signals: {signals_count}")
    
    # Count profiles
    profiles_count = await db.case_risk_profiles.count_documents({})
    print(f"🎯 Risk Profiles: {profiles_count}")
    
    # Show high-risk cases
    high_risk = await db.case_risk_profiles.find(
        {'risk_level': 'High'}
    ).to_list(length=10)
    
    print(f"\n⚠️  High-Risk Cases:")
    for profile in high_risk:
        print(f"  • {profile['case_user']}: {profile['risk_score']:.1f}/100")

await view_results()
```

### Use the API

```bash
# Get all risk profiles
curl http://localhost:8000/api/analytics/risk-profiles

# Get high-risk only
curl http://localhost:8000/api/analytics/risk-profiles?risk_level=High

# Get specific user
curl http://localhost:8000/api/analytics/risk-profiles/username

# Get statistics
curl http://localhost:8000/api/analytics/stats
```

## 📊 Expected Output

After running the pipeline, you should see:

**Stage 1:**
```
✅ NLP Signal Extraction completed
   • Text units processed: 234
   • Signals created: 189
   • CSV exported: nlp_signals_output.csv
   • Duration: 45.2s
```

**Stage 2:**
```
✅ Behavioral Feature Engineering completed
   • Case users processed: 12
   • Profiles created: 12
   • High-risk cases: 2
   • Duration: 8.1s
```

## 🔧 Troubleshooting

### Issue: "Module not found"
```bash
# Make sure you're in the right directory
cd backend
python -c "import sys; print(sys.path)"

# Add to PYTHONPATH if needed
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Issue: "CUDA out of memory"
```python
# Models will automatically use CPU if GPU unavailable
# To force CPU:
import torch
torch.device('cpu')
```

### Issue: "MongoDB connection timeout"
```bash
# Check your IP is whitelisted in MongoDB Atlas
# Test connection:
mongosh "mongodb+srv://cluster.mongodb.net" --username <user>
```

### Issue: Models downloading slowly
```python
# Models are cached in ~/.cache/huggingface/
# Check space:
du -sh ~/.cache/huggingface/

# Clear and re-download if needed:
rm -rf ~/.cache/huggingface/transformers
```

## 📈 Performance Tips

1. **Start Small**: Use `limit=10` for first runs to test
2. **Use GPU**: If available, models run 5-10x faster
3. **Batch Processing**: Process users in groups of 10-20
4. **Cache Models**: Models are cached after first download
5. **Monitor Memory**: Close other applications during processing

## 🎯 Next Steps

1. ✅ Run the pipeline on sample data
2. ✅ Review risk profiles in the database
3. ✅ Integrate with the dashboard frontend
4. ✅ Set up scheduled pipeline runs (cron)
5. ✅ Configure alert thresholds
6. ✅ Train team on interpreting results

## 📚 Documentation

- **Full Documentation**: See `ANALYTICS_README.md`
- **Demo Notebook**: `analytics_demo.ipynb`
- **API Docs**: http://localhost:8000/docs (when server running)
- **Model Details**: Links in main README

## 🆘 Getting Help

If you encounter issues:

1. Check the troubleshooting section above
2. Review logs in terminal output
3. Test MongoDB connection separately
4. Verify environment variables in `.env`
5. Check model downloads in `~/.cache/huggingface/`

## 💡 Usage Examples

### Process Specific Users
```python
await run_nlp_extraction(case_users=['user1', 'user2'])
await run_feature_engineering(case_users=['user1', 'user2'])
```

### Change Time Window
```python
# Analyze last 30 days instead of 7
await run_feature_engineering(window_days=30)
```

### Export Results
```python
# Signals are auto-exported to CSV
# Risk profiles stay in MongoDB
# Query via API or directly from database
```

---

**Ready to start? Open `analytics_demo.ipynb` and follow along! 🚀**
