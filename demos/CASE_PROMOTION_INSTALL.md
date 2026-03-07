# Installation Guide for Case Promotion Integration

## Prerequisites

- Python 3.10+
- MongoDB connection
- Existing NLP pipeline setup

## Installation Steps

### 1. Install Dependencies

The integration requires the `schedule` package for automated execution.

**Using Poetry (recommended):**
```bash
cd backend
poetry add schedule
```

**Using pip:**
```bash
cd backend
pip install schedule
```

### 2. Verify MongoDB Collections

Ensure these collections exist and have indexes:
```bash
python database_setup/scs_mongodb_setup.py
```

This creates:
- `scs_cases`
- `scs_case_history`
- `scs_checklist`
- `scs_checklist_templates`
- `scs_users`
- Plus necessary indexes

### 3. Initialize Checklist Templates

Templates are required for auto-creating checklists on new cases.

**Option A: Use test script (creates defaults automatically)**
```bash
cd backend
python test_case_promotion.py
```

**Option B: Run manual setup**
```bash
python database_setup/scs_seed.py
```

### 4. Configure Environment Variables

Add to your `.env` file:
```bash
# MongoDB Connection
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/
SCS_DB_NAME=dellinnovate

# Scheduler Configuration
SCHEDULE_INTERVAL_HOURS=6
USE_LLM_CALIBRATION=true
ANALYTICS_WINDOW_DAYS=30
MIN_CASE_PRIORITY=medium

# Ollama (if using LLM calibration)
OLLAMA_URL=http://localhost:11434
```

### 5. Test the Integration

```bash
cd backend
python test_case_promotion.py
```

Expected output:
```
📊 Step 1: Checking analytics data...
Found 12 risk profiles in case_risk_profiles

🚀 Step 4: Running promotion (test with limit=5)...

✅ Promotion Results:
  Cases created: 5
  Cases updated: 0
  History entries added: 5
  Checklist items created: 20

✓ Test Complete!
```

### 6. Start the Backend Server

```bash
cd backend
poetry run uvicorn app:app --reload --port 8000
```

Or if using the development script:
```bash
bash start_dev.sh
```

### 7. Test API Endpoints

```bash
# Test promotion
curl -X POST http://localhost:8000/api/analytics/promote-to-cases \
  -H "Content-Type: application/json" \
  -d '{"min_priority": "medium", "limit": 5}'

# View cases
curl http://localhost:8000/api/analytics/cases/summary
```

### 8. Start Automated Scheduler (Optional)

For production, run the scheduler for automatic 6-hour cycles:

```bash
cd backend
python pipeline_scheduler.py
```

This will:
- Run the full pipeline immediately
- Schedule subsequent runs every 6 hours
- Log to console and `logs/pipeline_scheduler.log`

## Verification Checklist

- [ ] Dependencies installed (check `schedule` package)
- [ ] MongoDB collections created with indexes
- [ ] Checklist templates populated (4 default templates)
- [ ] Environment variables configured
- [ ] Test script runs successfully
- [ ] Backend server starts without errors
- [ ] API endpoints respond correctly
- [ ] Scheduler runs without errors (if using)

## Troubleshooting

### Module Not Found: schedule
```bash
pip install schedule
# or
poetry add schedule
```

### No Checklist Templates
Run the test script which auto-creates them, or manually insert via MongoDB.

### No Risk Profiles to Promote
First run the NLP pipeline:
```bash
curl -X POST http://localhost:8000/api/analytics/run-full-pipeline \
  -H "Content-Type: application/json" \
  -d '{
    "window_days": 30,
    "use_llm": false,
    "promote_to_cases": false
  }'
```

Then run promotion:
```bash
curl -X POST http://localhost:8000/api/analytics/promote-to-cases \
  -H "Content-Type: application/json" \
  -d '{"min_priority": "low"}'
```

### MongoDB Connection Errors
Verify `.env` has correct `MONGODB_URI` and `SCS_DB_NAME`.

## Next Steps

Once installation is verified:

1. **Development:** Use test script and API endpoints
2. **Production:** Deploy scheduler as systemd service or Docker container
3. **Monitoring:** Check `pipeline_execution_log` collection for run history
4. **Frontend:** Connect dashboard to read from `scs_cases` collection

## Support Files

All integration files are located in the `backend/` directory:

- **Service:** `services/case_promotion.py`
- **API:** `routes/analytics_routes.py` (new endpoints added)
- **Models:** `models/instagram_models.py` (SCS models added)
- **Scheduler:** `pipeline_scheduler.py`
- **Test:** `test_case_promotion.py`
- **Docs:** `CASE_PROMOTION_INTEGRATION.md`, `CASE_PROMOTION_QUICKREF.md`
