# NLP Analytics to SCS Case Management Integration

## Overview

This integration bridges the **NLP analytics layer** (risk detection) with the **operational SCS case management layer** (youth worker interventions).

**Data Flow:**
```
Instagram Data → NLP Analysis → Risk Profiles → SCS Cases → Youth Workers
     ↓               ↓              ↓              ↓             ↓
instagram_*    text_units_    case_risk_     scs_cases     Dashboard
collections     signals        profiles       scs_case_     & Workflow
                                              history
                                              scs_checklist
```

## Architecture

### Layer A: Analytics (Input)
- **Collections:** `instagram_users`, `instagram_posts`, `instagram_comments`
- **Purpose:** Raw scraped social media data

### Layer B: NLP Processing (Intermediate)
- **Collections:** `text_units_signals`, `case_risk_profiles`
- **Purpose:** AI-generated risk assessments and evidence

### Layer C: Operational (Output)  
- **Collections:** `scs_cases`, `scs_case_history`, `scs_checklist`
- **Purpose:** Case management for youth workers

## Key Components

### 1. Case Promotion Service
**File:** `backend/services/case_promotion.py`

Transforms analytics outputs into operational case records.

**Functions:**
- `promote_risk_profiles_to_scs_cases()` - Main promotion function
- `CasePromotionService` - Full service class with upsert logic

**Logic:**
1. Read latest risk profiles from `case_risk_profiles`
2. Filter by priority threshold (configurable)
3. For each profile:
   - **New case:** Create in `scs_cases`, add to `scs_case_history`, initialize `scs_checklist`
   - **Existing case:** Update `scs_cases`, append to `scs_case_history`

### 2. API Endpoints
**File:** `backend/routes/analytics_routes.py`

**New Endpoints:**

#### POST `/api/analytics/promote-to-cases`
Manually trigger case promotion.

**Request:**
```json
{
  "min_priority": "medium",
  "limit": null
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Promoted 5 new cases, updated 3 existing cases",
  "results": {
    "profiles_read": 12,
    "profiles_filtered": 8,
    "cases_created": 5,
    "cases_updated": 3,
    "history_entries_added": 8,
    "checklist_items_created": 20,
    "errors": []
  },
  "started_at": "2026-03-07T10:30:00Z"
}
```

#### POST `/api/analytics/run-full-pipeline`
Run complete end-to-end pipeline (NLP → Scoring → Promotion).

**Request:**
```json
{
  "case_users": null,
  "window_days": 30,
  "use_llm": true,
  "llm_model": "llama2",
  "min_priority": "medium",
  "promote_to_cases": true
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Full pipeline completed in 45.2s",
  "results": {
    "stage1_nlp": { "text_units_processed": 234, ... },
    "stage2_scoring": { "n_profiles": 12, ... },
    "stage3_promotion": { "cases_created": 5, ... },
    "duration_seconds": 45.2,
    "pipeline_version": "v1.0-pca-llm"
  },
  "started_at": "2026-03-07T10:30:00Z"
}
```

#### GET `/api/analytics/cases/summary`
Get operational case summary.

**Query Parameters:**
- `priority` - Filter by priority level
- `case_status` - Filter by case status
- `limit` - Maximum results (default: 50)

**Response:**
```json
{
  "total_cases": 25,
  "critical_cases": 3,
  "unassigned_cases": 8,
  "filtered_count": 10,
  "cases": [...]
}
```

#### GET `/api/analytics/cases/{case_id}/history`
Get risk score evolution for a case.

**Response:**
```json
{
  "case": { "case_id": "CASE_2026_001", ... },
  "history_count": 5,
  "history": [
    {
      "history_id": 1,
      "case_id": "CASE_2026_001",
      "risk_score": 78.5,
      "category": "depression_risk",
      "ingestion_date": "2026-03-01T06:00:00Z",
      "model_version": "nlp-v1-pca-v1-llm-v1"
    },
    ...
  ]
}
```

### 3. Automated Scheduler
**File:** `backend/pipeline_scheduler.py`

Runs the full pipeline automatically every 6 hours.

**Usage:**
```bash
cd backend
python pipeline_scheduler.py
```

**Configuration (via .env):**
```bash
SCHEDULE_INTERVAL_HOURS=6
USE_LLM_CALIBRATION=true
ANALYTICS_WINDOW_DAYS=30
MIN_CASE_PRIORITY=medium
OLLAMA_URL=http://localhost:11434
```

**Features:**
- Automatic retries on failure
- Comprehensive logging
- Execution history tracking
- Graceful error handling

### 4. Data Models
**File:** `backend/models/instagram_models.py`

**New Models:**
- `SCSCaseModel` - Operational case record
- `SCSCaseHistoryModel` - Historical risk snapshots
- `SCSChecklistItemModel` - Task tracking
- `SCSChecklistTemplateModel` - Template definitions
- `SCSUserModel` - Staff users

## Database Schemas

### scs_cases
```javascript
{
  "case_id": "CASE_2026_001",           // Generated: CASE_{year}_{counter}
  "user_id": "@at_risk_teen_01",        // Social media handle
  "assigned_to": null,                   // staff user_id (null = unassigned)
  "current_risk_score": 78.5,           // 0-100 scale
  "category": "depression_risk",         // AI-determined category
  "ai_explanation": "Frequent negative affect...",
  "case_status": "unassigned",          // unassigned | assigned
  "work_status": "not_started",         // not_started | in_progress | to_review | completed
  "priority": "high",                   // low | medium | high | critical
  "created_at": ISODate("..."),
  "updated_at": ISODate("...")
}
```

### scs_case_history
```javascript
{
  "history_id": 1,                      // Auto-increment
  "case_id": "CASE_2026_001",
  "risk_score": 75.4,
  "category": "depression_risk",
  "ai_explanation": "Early signs show...",
  "ingestion_date": ISODate("..."),    // Ingestion cycle timestamp
  "model_version": "nlp-v1-pca-v1-llm-v1"
}
```

### scs_checklist
```javascript
{
  "checklist_item_id": 1,              // Auto-increment
  "case_id": "CASE_2026_001",
  "template_id": 1,                     // null for custom items
  "label": "Case Analysis Completed",
  "is_mandatory": true,
  "completed": false,
  "comments": [
    {
      "comment": "Initial analysis done",
      "timestamp": "2026-03-01T10:30:00",
      "by": "helper_001"
    }
  ],
  "completed_at": null,
  "completed_by": null,
  "display_order": 1,
  "created_at": ISODate("...")
}
```

### scs_checklist_templates
```javascript
{
  "template_id": 1,
  "label": "Case Analysis Completed",
  "is_mandatory": true,
  "display_order": 1,
  "is_active": true,
  "created_at": ISODate("...")
}
```

**Default Templates:**
1. Case Analysis Completed
2. Outreach Attempted
3. Response Received
4. Follow-up Scheduled

## Field Mappings

### Analytics → SCS Cases

| Analytics Field | SCS Field | Transformation |
|----------------|-----------|----------------|
| `case_user` | `user_id` | Direct |
| `final_score` (0-1) | `current_risk_score` | × 100 |
| `priority_level` | `priority` | Direct |
| Category (inferred) | `category` | Extracted |
| Explanation | `ai_explanation` | Built from components |
| - | `case_id` | Generated: CASE_{year}_{seq} |
| - | `assigned_to` | null (initially) |
| - | `case_status` | "unassigned" |
| - | `work_status` | "not_started" |

### Priority Filtering

**Priority Levels (from analytics):**
- `low` → Background monitoring
- `medium` → Active case
- `high` → Priority case
- `critical` → Immediate attention

**Configuration:**
```python
min_priority = "medium"  # Create cases for medium/high/critical only
```

## Upsert Logic

### New Case Creation
1. Generate `case_id` (e.g., `CASE_2026_001`)
2. Insert into `scs_cases` with defaults:
   - `assigned_to` = null
   - `case_status` = "unassigned"
   - `work_status` = "not_started"
3. Insert history entry into `scs_case_history`
4. Create mandatory checklist items from `scs_checklist_templates`

### Existing Case Update
1. Update **AI-driven fields only**:
   - `current_risk_score`
   - `category`
   - `ai_explanation`
   - `priority`
   - `updated_at`
2. **Preserve workflow fields:**
   - `assigned_to` (don't reset assignment)
   - `case_status` (don't reset status)
   - `work_status` (don't reset progress)
3. Append new history entry to `scs_case_history`
4. **Do NOT recreate checklist** (preserve progress)

## Testing

### Prerequisites
1. MongoDB connection configured in `.env`
2. Checklist templates populated
3. At least one risk profile in `case_risk_profiles`

### Run Test Script
```bash
cd backend
python test_case_promotion.py
```

**Test Steps:**
1. Check analytics data availability
2. Verify SCS tables before promotion
3. Check checklist templates (creates defaults if missing)
4. Run promotion with limit=5
5. Verify SCS tables after promotion
6. Show created cases and history

**Expected Output:**
```
📊 Step 1: Checking analytics data...
Found 12 risk profiles in case_risk_profiles

📋 Step 2: Checking SCS tables (before)...
  Cases: 0
  History entries: 0
  Checklist items: 0

🚀 Step 4: Running promotion (test with limit=5)...

✅ Promotion Results:
  Profiles read: 12
  Profiles filtered: 8
  Cases created: 5
  Cases updated: 0
  History entries added: 5
  Checklist items created: 20

✓ Test Complete!
```

### Test API Endpoints

**Test promotion endpoint:**
```bash
curl -X POST http://localhost:8000/api/analytics/promote-to-cases \
  -H "Content-Type: application/json" \
  -d '{"min_priority": "medium", "limit": 5}'
```

**Test full pipeline:**
```bash
curl -X POST http://localhost:8000/api/analytics/run-full-pipeline \
  -H "Content-Type: application/json" \
  -d '{
    "window_days": 30,
    "use_llm": true,
    "min_priority": "medium",
    "promote_to_cases": true
  }'
```

**View cases:**
```bash
curl http://localhost:8000/api/analytics/cases/summary?priority=high
```

**View case history:**
```bash
curl http://localhost:8000/api/analytics/cases/CASE_2026_001/history
```

## Deployment

### 1. Manual Execution
```bash
cd backend
python -c "
import asyncio
from services.case_promotion import promote_risk_profiles_to_scs_cases
from config.database import MongoDB

async def run():
    await MongoDB.connect_db()
    db = MongoDB.get_db()
    result = await promote_risk_profiles_to_scs_cases(db)
    print(result)
    await MongoDB.close_db()

asyncio.run(run())
"
```

### 2. Scheduled Execution (Recommended)
```bash
cd backend
python pipeline_scheduler.py
```

Runs every 6 hours automatically. Logs to:
- Console (stderr)
- `logs/pipeline_scheduler.log` (rotated daily, 30-day retention)

### 3. Cron Job (Alternative)
```bash
# Add to crontab: Run every 6 hours
0 */6 * * * cd /path/to/backend && python pipeline_scheduler.py >> logs/cron.log 2>&1
```

### 4. Docker/Systemd Service
Create systemd service file: `/etc/systemd/system/scs-pipeline.service`

```ini
[Unit]
Description=SCS Analytics Pipeline Scheduler
After=network.target mongodb.service

[Service]
Type=simple
User=scsuser
WorkingDirectory=/path/to/backend
ExecStart=/usr/bin/python3 pipeline_scheduler.py
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable scs-pipeline
sudo systemctl start scs-pipeline
sudo systemctl status scs-pipeline
```

## Monitoring

### Pipeline Execution Log
The scheduler logs each run to `pipeline_execution_log` collection:

```javascript
{
  "run_id": "20260307_103000",
  "timestamp": ISODate("..."),
  "start_time": ISODate("..."),
  "duration_seconds": 45.2,
  "status": "success",
  "stage1_results": {...},
  "stage2_results": {...},
  "stage3_results": {...}
}
```

### Query Execution History
```javascript
db.pipeline_execution_log.find().sort({timestamp: -1}).limit(10)
```

### Check for Failures
```javascript
db.pipeline_execution_log.find({status: "failed"})
```

## Troubleshooting

### No Cases Created

**Check 1: Risk profiles exist?**
```javascript
db.case_risk_profiles.countDocuments()
```

**Check 2: Priority threshold too high?**
```javascript
// See priority distribution
db.case_risk_profiles.aggregate([
  {$group: {_id: "$priority_level", count: {$sum: 1}}}
])
```

Lower `min_priority` parameter.

**Check 3: Checklist templates missing?**
```javascript
db.scs_checklist_templates.countDocuments({is_active: true})
```

Run test script to create defaults.

### Duplicate Cases

Cases should not duplicate (upsert based on `user_id`).

**Check for duplicates:**
```javascript
db.scs_cases.aggregate([
  {$group: {_id: "$user_id", count: {$sum: 1}}},
  {$match: {count: {$gt: 1}}}
])
```

If found, this is a bug - report with logs.

### Missing History Entries

Each ingestion cycle should create history entries.

**Check history count:**
```javascript
db.scs_case_history.countDocuments({case_id: "CASE_2026_001"})
```

**Verify promotion is running:**
```bash
tail -f logs/pipeline_scheduler.log | grep "Stage 3"
```

## Performance Considerations

### Large Databases
- Enable MongoDB indexes (auto-created by `scs_mongodb_setup.py`)
- Use `limit` parameter during testing
- Monitor execution time per stage

### Concurrent Runs
- Scheduler prevents overlapping runs
- If manual execution, ensure only one process runs at a time

### Scaling
- Analytics pipeline is CPU-bound (NLP models)
- Promotion service is I/O-bound (database writes)
- Consider separate workers for each stage

## Environment Variables

Add to your `.env` file:

```bash
# Scheduler Configuration
SCHEDULE_INTERVAL_HOURS=6
USE_LLM_CALIBRATION=true
ANALYTICS_WINDOW_DAYS=30
MIN_CASE_PRIORITY=medium

# Ollama Configuration (if using LLM)
OLLAMA_URL=http://localhost:11434

# MongoDB Connection
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/
SCS_DB_NAME=dellinnovate
```

## Summary

This integration creates a **production-ready bridge** between AI risk detection and operational case management:

✅ **Automated:** Runs every 6 hours via scheduler  
✅ **Traceable:** Full history of risk score changes  
✅ **Worker-Ready:** Cases appear in dashboard immediately  
✅ **Auditable:** Every ingestion cycle logged  
✅ **Idempotent:** Safe to re-run without duplicates  
✅ **Configurable:** Priority thresholds, time windows, LLM usage  

**Next Steps:**
1. Run test script: `python test_case_promotion.py`
2. Start scheduler: `python pipeline_scheduler.py`
3. Monitor logs: `tail -f logs/pipeline_scheduler.log`
4. View cases in dashboard: Frontend `/cases` route
