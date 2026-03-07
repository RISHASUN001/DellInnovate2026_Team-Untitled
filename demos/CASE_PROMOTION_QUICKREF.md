# Case Promotion Quick Reference

## 🚀 Quick Start Commands

### 1. Test Case Promotion
```bash
cd backend
python test_case_promotion.py
```

### 2. Run Full Pipeline (Manual)
```bash
curl -X POST http://localhost:8000/api/analytics/run-full-pipeline \
  -H "Content-Type: application/json" \
  -d '{
    "window_days": 30,
    "use_llm": true,
    "promote_to_cases": true
  }'
```

### 3. Start Automated Scheduler
```bash
cd backend
python pipeline_scheduler.py
```

### 4. Promote Existing Profiles
```bash
curl -X POST http://localhost:8000/api/analytics/promote-to-cases \
  -H "Content-Type: application/json" \
  -d '{"min_priority": "medium"}'
```

---

## 📊 View Cases & History

### Get Cases Summary
```bash
curl http://localhost:8000/api/analytics/cases/summary
```

### Filter by Priority
```bash
curl "http://localhost:8000/api/analytics/cases/summary?priority=critical&limit=10"
```

### View Case History
```bash
curl http://localhost:8000/api/analytics/cases/CASE_2026_001/history
```

---

## 🗄️ Database Queries

### Count Cases
```javascript
db.scs_cases.countDocuments()
db.scs_case_history.countDocuments()
db.scs_checklist.countDocuments()
```

### View Recent Cases
```javascript
db.scs_cases.find().sort({created_at: -1}).limit(5)
```

### Case Priority Distribution
```javascript
db.scs_cases.aggregate([
  {$group: {_id: "$priority", count: {$sum: 1}}}
])
```

### Unassigned Critical Cases
```javascript
db.scs_cases.find({
  priority: "critical",
  case_status: "unassigned"
}).sort({current_risk_score: -1})
```

### Risk Score Trend for Case
```javascript
db.scs_case_history.find({case_id: "CASE_2026_001"})
  .sort({ingestion_date: 1})
```

---

## 🔧 Setup Tasks

### Initialize Checklist Templates
Run test script or manual insert:
```javascript
db.scs_checklist_templates.insertMany([
  {
    template_id: 1,
    label: "Case Analysis Completed",
    is_mandatory: true,
    display_order: 1,
    is_active: true,
    created_at: new Date()
  },
  {
    template_id: 2,
    label: "Outreach Attempted",
    is_mandatory: true,
    display_order: 2,
    is_active: true,
    created_at: new Date()
  },
  {
    template_id: 3,
    label: "Response Received",
    is_mandatory: true,
    display_order: 3,
    is_active: true,
    created_at: new Date()
  },
  {
    template_id: 4,
    label: "Follow-up Scheduled",
    is_mandatory: true,
    display_order: 4,
    is_active: true,
    created_at: new Date()
  }
])
```

---

## 📈 Monitoring

### View Pipeline Execution Log
```javascript
db.pipeline_execution_log.find().sort({timestamp: -1}).limit(5)
```

### Check for Failed Runs
```javascript
db.pipeline_execution_log.find({status: "failed"})
```

### Latest Pipeline Statistics
```javascript
db.pipeline_execution_log.findOne({status: "success"}, {sort: {timestamp: -1}})
```

---

## 🐛 Troubleshooting

### No risk profiles found
```bash
# Run NLP pipeline first
curl -X POST http://localhost:8000/api/analytics/compute-risk-profiles-pca \
  -H "Content-Type: application/json" \
  -d '{"window_days": 30, "use_llm": false}'
```

### Check analytics data
```javascript
db.case_risk_profiles.countDocuments()
db.text_units_signals.countDocuments()
```

### Reset counters (if needed)
```javascript
db.counters.deleteMany({})
```

### Clear test data
```javascript
db.scs_cases.deleteMany({})
db.scs_case_history.deleteMany({})
db.scs_checklist.deleteMany({})
```

---

## 🔄 Complete Workflow Example

```bash
# 1. Scrape Instagram data (if not done)
curl -X POST http://localhost:8000/api/scraper/scrape \
  -H "Content-Type: application/json" \
  -d '{"usernames": ["test_user"], "scrape_posts": true}'

# 2. Run full pipeline
curl -X POST http://localhost:8000/api/analytics/run-full-pipeline \
  -H "Content-Type: application/json" \
  -d '{
    "window_days": 30,
    "use_llm": true,
    "min_priority": "medium",
    "promote_to_cases": true
  }'

# 3. View created cases
curl http://localhost:8000/api/analytics/cases/summary

# 4. View a specific case history
curl http://localhost:8000/api/analytics/cases/CASE_2026_001/history
```

---

## 📝 Environment Variables

```bash
# Add to .env
SCHEDULE_INTERVAL_HOURS=6
USE_LLM_CALIBRATION=true
ANALYTICS_WINDOW_DAYS=30
MIN_CASE_PRIORITY=medium
OLLAMA_URL=http://localhost:11434
```

---

## 🎯 Priority Thresholds

| min_priority | Creates cases for |
|--------------|-------------------|
| `low` | All risk levels |
| `medium` | Medium, High, Critical |
| `high` | High, Critical |
| `critical` | Critical only |

---

## 📁 Key Files

| File | Purpose |
|------|---------|
| `services/case_promotion.py` | Promotion service logic |
| `routes/analytics_routes.py` | API endpoints |
| `pipeline_scheduler.py` | Automated scheduler |
| `test_case_promotion.py` | Test script |
| `models/instagram_models.py` | Data models |
| `CASE_PROMOTION_INTEGRATION.md` | Full documentation |
