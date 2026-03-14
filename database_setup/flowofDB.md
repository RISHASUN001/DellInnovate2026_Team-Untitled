# 📊 SCS Youth Helper Dashboard - Database Architecture

## 🗄️ Database Overview

**Database Name:** `dellinnovate`  
**Platform:** MongoDB Atlas  
**Connection:** Cloud-hosted cluster

---

## 🔗 Connection Setup

### Environment Variables (.env)
```env
MONGODB_URI=mongodb+srv://username:password@cluster0.1yrcnpc.mongodb.net/dellinnovate?retryWrites=true&w=majority
SCS_DB_NAME=dellinnovate

---
.env file
    ↓
Python app loads dotenv
    ↓
MongoClient connects using MONGODB_URI
    ↓
Access database using SCS_DB_NAME
    ↓
Ready to query collections
--

📦 Collections Structure
1. scs_users (User Management)
Stores all system users (admins and youth helpers).

{
  "_id": ObjectId(),
  "user_id": "helper_001",           // Unique identifier
  "username": "Alex Johnson",        // Display name
  "role": "youth_helper",            // "admin" or "youth_helper"
  "email": "alex@example.com",
  "is_active": true,
  "created_at": ISODate(),
  "updated_at": ISODate()
}

Indexes:

user_id (unique)
role
is_active

---
2. scs_cases (Main Case Management)
Central collection for all mental health cases.

{
  "_id": ObjectId(),
  "case_id": "CASE_2026_001",           // Unique case identifier
  "user_id": "@at_risk_teen_01",        // Instagram username
  "assigned_to": "helper_001",          // youth_helper user_id (null if unassigned)
  "current_risk_score": 78.5,           // 0-100 risk score
  "current_category": "Moderate Risk - Depression",
  "current_risk_signals": "Multiple posts expressing sadness",
  "case_status": "assigned",            // "unassigned" or "assigned"
  "work_status": "in_progress",         // "not_started", "in_progress", "to_review", "completed"
  "priority": "medium",                 // "low", "medium", "high", "critical"
  "created_at": ISODate(),
  "updated_at": ISODate()
}

Indexes:

case_id (unique)
user_id
assigned_to
case_status
priority
---
Case Status Flow:
NEW CASE
    ↓
unassigned → (admin assigns) → assigned
                                    ↓
                          work_status transitions:
                          not_started → in_progress → to_review → completed

---
3. scs_case_history (Risk Score Timeline)
Tracks how a case's risk evolves over time (created by ML re-ingestion).
{
  "_id": ObjectId(),
  "history_id": 1,                      // Auto-increment ID
  "case_id": "CASE_2026_001",           // Links to scs_cases
  "risk_score": 78.5,                   // Risk score at this time
  "category": "Moderate Risk - Depression",
  "risk_signals": "Multiple posts expressing sadness",
  "ingestion_date": ISODate()           // When ML model ran
}
Indexes:

case_id
ingestion_date (descending)
Purpose:

Shows risk trend over time (improving/worsening)
Multiple entries per case (one per ML ingestion)
Used for charts/graphs in dashboard
Example Timeline:
{
  "_id": ObjectId(),
  "template_id": 1,                     // Unique template ID
  "label": "Case Analysis Completed",
  "is_mandatory": true,                 // Must be in every case
  "display_order": 1,                   // Order in UI
  "is_active": true,                    // Can be deactivated
  "created_at": ISODate()
}

---
4. scs_checklist_templates (Mandatory Steps)
Defines required checklist items that every case must have.

Default Templates:
{
  "_id": ObjectId(),
  "template_id": 1,                     // Unique template ID
  "label": "Case Analysis Completed",
  "is_mandatory": true,                 // Must be in every case
  "display_order": 1,                   // Order in UI
  "is_active": true,                    // Can be deactivated
  "created_at": ISODate()
}

Case Analysis Completed
Outreach Attempted
Response Received
Follow-up Scheduled

---
5. scs_checklist (Case Action Items)
Individual checklist items for each case (auto-created from templates + custom).
{
  "_id": ObjectId(),
  "checklist_item_id": 1,               // Auto-increment ID
  "case_id": "CASE_2026_001",           // Links to scs_cases
  "template_id": 1,                     // Links to template (null if custom)
  "label": "Case Analysis Completed",
  "is_mandatory": true,
  "completed": false,
  "comments": [                         // Array of comments
    {
      "comment": "Initial analysis done",
      "timestamp": "2026-03-01T10:00:00Z",
      "by": "helper_001"
    }
  ],
  "completed_at": null,                 // ISODate when completed
  "completed_by": null,                 // user_id who completed it
  "display_order": 1,
  "created_at": ISODate()
}

Indexes:

checklist_item_id (unique)
case_id
Checklist Creation Flow:
New Case Created
    ↓
System reads scs_checklist_templates
    ↓
For each active template:
  → Create checklist item in scs_checklist
  → Link to case_id
  → Set completed = false
    ↓
Youth Helper can add custom items
    ↓
Youth Helper completes items
  → completed = true
  → completed_by = helper_id
  → completed_at = timestamp

Example:
CASE_2026_004 Checklist:
  ☑ Case Analysis Completed (mandatory, from template)
  ☑ Outreach Attempted (mandatory, from template)
  ☐ Response Received (mandatory, from template)
  ☐ Follow-up Scheduled (mandatory, from template)
  ☐ Contact school counselor (custom, optional)
  ☐ Share anxiety resources (custom, optional)

6. scs_review_requests (Helper → Admin Communication)
When youth helpers need guidance on complex cases.
{
  "_id": ObjectId(),
  "review_id": 1,                       // Auto-increment ID
  "case_id": "CASE_2026_007",           // Case needing review
  "requested_by": "helper_001",         // Helper requesting guidance
  "reason": "Multiple risk factors, need guidance",
  "request_status": "pending",          // "pending" or "resolved"
  "requested_at": ISODate(),
  "resolved_by": "admin_001",           // Admin who resolved (null if pending)
  "resolved_at": ISODate(),             // When resolved (null if pending)
  "resolution_notes": "Escalate to emergency services"
}

Indexes:

review_id (unique)
case_id
request_status
Review Request Flow:
Youth Helper encounters complex case
    ↓
Clicks "Request Review"
    ↓
Creates review_request (status: pending)
    ↓
Admin sees in dashboard
    ↓
Admin provides guidance
    ↓
Updates request (status: resolved)
    ↓
Helper receives notification

---
7. scs_reassignment_requests (Workload Management)
Request to transfer case to another youth helper.
{
  "_id": ObjectId(),
  "request_id": 1,                      // Auto-increment ID
  "case_id": "CASE_2026_010",           // Case to reassign
  "requested_by": "helper_005",         // Current helper
  "current_assigned_to": "helper_005",
  "reason": "Case requires trauma-informed care beyond my expertise",
  "suggested_helper": "helper_003",     // Recommended new helper
  "request_status": "pending",          // "pending", "approved", "declined"
  "requested_at": ISODate(),
  "reviewed_by": "admin_001",           // Admin who reviewed
  "reviewed_at": ISODate(),
  "new_assigned_to": "helper_003",      // Approved new helper
  "review_notes": "Approved due to expertise match"
}

Indexes:

request_id (unique)
case_id
request_status
Reassignment Flow:
Helper requests reassignment
    ↓
Creates reassignment_request
    ↓
Admin reviews request
    ↓
    ├─→ Approved
    │     ↓
    │   Update scs_cases.assigned_to
    │     ↓
    │   Notify new helper
    │
    └─→ Declined
          ↓
        Case stays with current helper

---
🔄 Complete Data Flow
📥 Case Lifecycle
┌──────────────────────────────────────────────────────────────┐
│                    1. CASE INGESTION                         │
└──────────────────────────────────────────────────────────────┘
ML Model analyzes Instagram data
    ↓
Creates entry in scs_cases
    - case_status: "unassigned"
    - work_status: "not_started"
    - current_risk_score: 78.5
    - priority: "medium"
    ↓
Auto-creates checklist items from templates
    ↓
Creates initial scs_case_history entry

┌──────────────────────────────────────────────────────────────┐
│                    2. CASE ASSIGNMENT                        │
└──────────────────────────────────────────────────────────────┘
Admin views unassigned cases in dashboard
    ↓
Selects youth helper based on:
    - Current workload
    - Expertise
    - Availability
    ↓
Updates scs_cases:
    - case_status: "assigned"
    - assigned_to: "helper_001"
    ↓
Helper receives notification

┌──────────────────────────────────────────────────────────────┐
│                    3. HELPER WORKS CASE                      │
└──────────────────────────────────────────────────────────────┘
Helper opens case dashboard
    ↓
Reviews:
    - Current risk score
    - Risk signals
    - Case history (risk trend)
    - Mandatory checklist
    ↓
Updates work_status: "in_progress"
    ↓
Completes checklist items:
    ☑ Case Analysis Completed
    ☑ Outreach Attempted
    ↓
Adds custom checklist items (optional):
    ☐ Contact school counselor
    ☐ Share resources
    ↓
Adds comments to checklist items
    ↓
If complex case:
    → Creates scs_review_requests entry
    → Waits for admin guidance
    ↓
If needs reassignment:
    → Creates scs_reassignment_requests entry
    → Waits for admin decision

┌──────────────────────────────────────────────────────────────┐
│                    4. ML RE-INGESTION                        │
└──────────────────────────────────────────────────────────────┘
ML model runs again (daily/weekly)
    ↓
Analyzes updated Instagram data
    ↓
Creates new scs_case_history entry
    - risk_score: 71.4 (changed!)
    - category: "Moderate Risk - Social Isolation"
    ↓
Updates scs_cases.current_risk_score
    ↓
Helper sees updated risk in dashboard
    ↓
Risk trend chart shows:
    Day 1: 62.1 → Day 3: 68.3 → Day 5: 71.4 (worsening)

┌──────────────────────────────────────────────────────────────┐
│                    5. ADMIN OVERSIGHT                        │
└──────────────────────────────────────────────────────────────┘
Admin dashboard shows:
    - Pending review requests
    - Pending reassignment requests
    - Helper workload stats
    - Case priority distribution
    ↓
Processes review requests:
    - Reads helper's concern
    - Provides guidance
    - Updates request_status: "resolved"
    ↓
Processes reassignment requests:
    - Reviews reason
    - Checks suggested helper's workload
    - Approves or declines
    - If approved: updates scs_cases.assigned_to

┌──────────────────────────────────────────────────────────────┐
│                    6. CASE COMPLETION                        │
└──────────────────────────────────────────────────────────────┘
All mandatory checklist items completed
    ↓
Helper marks work_status: "to_review"
    ↓
Admin reviews case
    ↓
If satisfactory:
    - work_status: "completed"
    - Case closed
    ↓
Case remains in database for:
    - Historical reference
    - Analytics
    - Reporting

---
scs_users (1) ──→ (many) scs_cases [assigned_to]
                     ↓
                     ├──→ (many) scs_case_history [case_id]
                     ├──→ (many) scs_checklist [case_id]
                     ├──→ (0-many) scs_review_requests [case_id]
                     └──→ (0-many) scs_reassignment_requests [case_id]

scs_checklist_templates (1) ──→ (many) scs_checklist [template_id]

---
┌─────────────┐
│  scs_users  │
└──────┬──────┘
       │ assigned_to
       ↓
┌─────────────┐     case_id      ┌──────────────────────┐
│  scs_cases  │ ────────────────→ │ scs_case_history     │
└──────┬──────┘                   └──────────────────────┘
       │ case_id
       ├────────────────────────→ ┌──────────────────────┐
       │                          │ scs_checklist        │
       │                          └──────────┬───────────┘
       │                                     │ template_id
       │                          ┌──────────┴───────────┐
       │                          │ scs_checklist_       │
       │                          │ templates            │
       │                          └──────────────────────┘
       │
       ├────────────────────────→ ┌──────────────────────┐
       │                          │ scs_review_requests  │
       │                          └──────────────────────┘
       │
       └────────────────────────→ ┌──────────────────────┐
                                  │ scs_reassignment_    │
                                  │ requests             │
                                  └──────────────────────┘