# 🎯 Case Promotion Integration - README

## What Was Implemented

A complete integration layer that connects your **NLP analytics pipeline** to the **operational SCS case management system**.

**Before:** Analytics outputs stayed in analytics collections  
**After:** Analytics outputs automatically become actionable cases for youth workers

---

## 📂 Files Created

### Core Implementation
1. **`backend/services/case_promotion.py`** - Promotion service
2. **`backend/routes/analytics_routes.py`** - 4 new API endpoints added
3. **`backend/models/instagram_models.py`** - SCS models added
4. **`backend/pipeline_scheduler.py`** - Automated scheduler
5. **`backend/test_case_promotion.py`** - Test script

### Documentation
6. **`backend/CASE_PROMOTION_INTEGRATION.md`** - Complete technical guide
7. **`backend/CASE_PROMOTION_QUICKREF.md`** - Command reference
8. **`backend/CASE_PROMOTION_INSTALL.md`** - Installation guide
9. **`backend/IMPLEMENTATION_COMPLETE.md`** - Implementation summary
10. **`backend/pyproject.toml`** - Updated with `schedule` dependency

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd backend
poetry install
# This will install the new 'schedule' package
```

### 2. Test the Integration
```bash
python test_case_promotion.py
```

**Expected Output:**
```
✅ Promotion Results:
  Cases created: 5
  Cases updated: 0
  History entries added: 5
  Checklist items created: 20
✓ Test Complete!
```

### 3. Start Backend (if not running)
```bash
poetry run uvicorn app:app --reload --port 8000
```

### 4. Test API Endpoint
```bash
curl -X POST http://localhost:8000/api/analytics/run-full-pipeline \
  -H "Content-Type: application/json" \
  -d '{"promote_to_cases": true}'
```

### 5. View Created Cases
```bash
curl http://localhost:8000/api/analytics/cases/summary
```

### 6. Start Automated Scheduler (Optional)
```bash
python pipeline_scheduler.py
```

---

## 🔄 Data Flow

```
┌──────────────────────────────────────────────────────────────┐
│ STAGE 1: NLP Signal Extraction                               │
│ Input: instagram_posts, instagram_comments                   │
│ Output: text_units_signals                                   │
│ Process: Sentiment, emotion, distortion detection            │
└────────────────────────┬─────────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────────┐
│ STAGE 2: Risk Scoring (PCA + LLM)                           │
│ Input: text_units_signals                                    │
│ Output: case_risk_profiles                                   │
│ Process: Aggregation, PCA, LLM calibration                   │
└────────────────────────┬─────────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────────┐
│ STAGE 3: Case Promotion ⭐ NEW                               │
│ Input: case_risk_profiles                                    │
│ Output: scs_cases, scs_case_history, scs_checklist          │
│ Process: Upsert cases, append history, create checklists     │
└──────────────────────────────────────────────────────────────┘
```

---

## 🆕 New API Endpoints

### 1. Promote Risk Profiles to Cases
```bash
POST /api/analytics/promote-to-cases
```

### 2. Run Full Pipeline (End-to-End)
```bash
POST /api/analytics/run-full-pipeline
```

### 3. Get Operational Cases
```bash
GET /api/analytics/cases/summary?priority=high
```

### 4. Get Case History
```bash
GET /api/analytics/cases/{case_id}/history
```

---

## 🗄️ Database Collections

### Populated by Integration

#### `scs_cases` - Current case state
One record per monitored youth. Updated on each run.

#### `scs_case_history` - Historical snapshots  
One new record per case per ingestion cycle. Never deleted.

#### `scs_checklist` - Task tracking
4 items per new case (from templates). Never deleted.

---

## ⚙️ Configuration

Add to `.env`:
```bash
# Scheduler settings
SCHEDULE_INTERVAL_HOURS=6
USE_LLM_CALIBRATION=true
ANALYTICS_WINDOW_DAYS=30
MIN_CASE_PRIORITY=medium

# Ollama (if using LLM)
OLLAMA_URL=http://localhost:11434
```

---

## 📋 Checklist Templates Required

The integration auto-creates 4 mandatory checklist items for new cases:
1. Case Analysis Completed
2. Outreach Attempted
3. Response Received
4. Follow-up Scheduled

These are created automatically when you run `test_case_promotion.py`.

---

## 🔧 Upsert Logic

### New Case (First Time)
✅ Create `scs_cases` record  
✅ Create `scs_case_history` entry  
✅ Create 4 `scs_checklist` items  
✅ Set status: `unassigned` / `not_started`

### Existing Case (Subsequent Runs)
✅ Update `scs_cases` risk fields only  
❌ Do NOT reset `assigned_to`  
❌ Do NOT reset `case_status`  
❌ Do NOT reset `work_status`  
❌ Do NOT recreate checklist  
✅ Append new `scs_case_history` entry

This preserves youth worker progress while updating AI assessments.

---

## 📊 Testing Scenarios

### Scenario 1: First Run (No Existing Cases)
```bash
python test_case_promotion.py
```
Expected: Creates new cases, history, checklists

### Scenario 2: Subsequent Run (Update Existing)
```bash
# Run twice
python test_case_promotion.py
python test_case_promotion.py
```
Expected: First run creates, second run updates + adds history

### Scenario 3: API Integration
```bash
curl -X POST http://localhost:8000/api/analytics/promote-to-cases \
  -d '{"min_priority": "medium"}'
```

### Scenario 4: Full Pipeline
```bash
curl -X POST http://localhost:8000/api/analytics/run-full-pipeline \
  -d '{"promote_to_cases": true}'
```

---

## 🤝 Integration Points

### Frontend Dashboard
Read from these collections:
- `scs_cases` - Case list
- `scs_case_history` - Risk trends
- `scs_checklist` - Task tracking

### Case Service
The existing case-service should now read from MongoDB `scs_cases` instead of its own database.

### MCP Service
Can continue to operate on `scs_cases` for tool-based updates.

---

## 📈 What This Enables

### For the System
✅ **Automated case creation** from AI detection  
✅ **Historical tracking** of risk evolution  
✅ **Structured workflow** via checklists  
✅ **Audit trail** of all AI decisions  
✅ **Scheduled automation** every 6 hours

### For Youth Workers
✅ **No manual data entry** - cases appear automatically  
✅ **Priority sorting** - focus on high-risk first  
✅ **Risk context** - see trends over time  
✅ **Guided intervention** - checklist items  
✅ **AI transparency** - explanations included

---

## 🐛 Troubleshooting

### No cases created?
**Check:** Do risk profiles exist?
```javascript
db.case_risk_profiles.countDocuments()
```

**Solution:** Run NLP pipeline first
```bash
curl -X POST http://localhost:8000/api/analytics/compute-risk-profiles-pca \
  -d '{"window_days": 30, "use_llm": false}'
```

### Missing checklist templates?
**Solution:** Run test script (auto-creates)
```bash
python test_case_promotion.py
```

### Import errors?
**Solution:** Install dependencies
```bash
poetry install
```

---

## 📚 Documentation Reference

| Document | Purpose |
|----------|---------|
| **CASE_PROMOTION_INTEGRATION.md** | Full technical specification |
| **CASE_PROMOTION_QUICKREF.md** | Command cheat sheet |
| **CASE_PROMOTION_INSTALL.md** | Setup instructions |
| **IMPLEMENTATION_COMPLETE.md** | What was built summary |
| **This file (README.md)** | Quick start guide |

---

## ✅ Success Criteria

The integration is working when:

1. ✅ Test script completes without errors
2. ✅ API endpoints return 200 responses
3. ✅ Cases appear in `scs_cases` collection
4. ✅ History grows with each pipeline run
5. ✅ Checklist items are auto-created
6. ✅ Frontend dashboard shows cases

---

## 🎉 What's Next?

### Immediate
1. Run test: `python test_case_promotion.py`
2. Verify API: Test the `/promote-to-cases` endpoint
3. Check database: View `scs_cases` in MongoDB

### Short-term
1. Connect frontend dashboard to read `scs_cases`
2. Start scheduler for automation
3. Monitor first few automated runs

### Long-term  
1. Deploy scheduler as systemd service
2. Add dashboard for pipeline monitoring
3. Tune priority thresholds based on outcomes
4. Add auto-escalation for critical cases

---

## 🔗 Related Files

The case promotion integration works with:
- `analytics/signal_extraction.py` - Stage 1 NLP
- `analytics/stage2_pca_llm.py` - Stage 2 Scoring  
- `database_setup/scs_mongodb_setup.py` - Database setup
- `database_setup/scs_seed.py` - Sample data

---

## 📞 Support

If you encounter issues:
1. Check logs: `logs/pipeline_scheduler.log`
2. Review documentation: `CASE_PROMOTION_INTEGRATION.md`
3. Run test script: `python test_case_promotion.py`
4. Verify MongoDB collections exist

---

## 💡 Key Design Decisions

1. **MongoDB vs SQL** - Uses MongoDB for operational tables (matches analytics DB)
2. **Upsert Logic** - Preserves workflow state, updates AI fields only
3. **One case per user** - Keyed by social media handle (`user_id`)
4. **History append-only** - Never updates, always inserts
5. **Auto-checklist** - Created once from templates, never reset
6. **Priority filtering** - Configurable threshold for case creation

---

**Status:** ✅ **Complete and Ready for Testing**  
**Date:** March 7, 2026  
**Version:** 1.0

Start with `python test_case_promotion.py` and follow the on-screen instructions! 🚀
