"""
MongoDB-based case management routes for SCS Youth Helper Dashboard
"""
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Request, Body
from pydantic import BaseModel
from ..database import get_db, serialize_doc
from ..auth import get_current_user, require_admin, AuthUser

router = APIRouter(prefix="/cases", tags=["cases"])


# ─── Pydantic Models ──────────────────────────────────────────────────────────

class CaseAssignment(BaseModel):
    assigned_to: str


class CaseUpdate(BaseModel):
    work_status: Optional[str] = None
    priority: Optional[str] = None
    case_status: Optional[str] = None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _audit(db, actor: AuthUser, action: str, resource: str, detail: dict | None = None):
    """Write audit log"""
    audit_col = db['scs_audit_log']
    await audit_col.insert_one({
        "actor_id": actor.user_id,
        "actor_role": actor.role,
        "action": action,
        "resource": resource,
        "detail": detail,
        "created_at": _now_iso()
    })


# ─── List all cases (with filters) ────────────────────────────────────────────
@router.get("")
@router.get("/")
async def list_cases(
    request: Request,
    category: Optional[str] = None,
    case_status: Optional[str] = None,
    work_status: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to: Optional[str] = None,
):
    """
    List all cases (admin) or only assigned cases (helper).
    Supports filtering by category, status, priority, etc.
    """
    user = get_current_user(request)
    db = await get_db()
    cases_col = db['scs_cases']

    # Build MongoDB query filter
    query_filter = {}
    
    # Helpers can only see their assigned cases
    if user.is_helper:
        query_filter["assigned_to"] = user.user_id
    elif assigned_to:
        query_filter["assigned_to"] = assigned_to

    if category:
        query_filter["category"] = category
    if case_status:
        query_filter["case_status"] = case_status
    if work_status:
        query_filter["work_status"] = work_status
    if priority:
        query_filter["priority"] = priority

    # Query with sorting
    cursor = cases_col.find(query_filter).sort([
        ("priority", -1),  # critical, high, medium, low
        ("current_risk_score", -1),  # highest risk first
        ("created_at", -1)
    ])

    cases = []
    async for doc in cursor:
        cases.append(serialize_doc(doc))

    return cases


# ─── Get unassigned cases (admin only) ────────────────────────────────────────
@router.get("/unassigned")
async def list_unassigned_cases(request: Request):
    """Get all cases that are unassigned (admin only)"""
    user = await require_admin(request)
    db = await get_db()
    cases_col = db['scs_cases']

    cursor = cases_col.find({
        "$or": [
            {"case_status": "unassigned"},
            {"assigned_to": None},
            {"assigned_to": ""}
        ]
    }).sort([
        ("current_risk_score", -1),
        ("created_at", -1)
    ])

    cases = []
    async for doc in cursor:
        cases.append(serialize_doc(doc))

    return cases


# ─── Get single case detail ───────────────────────────────────────────────────
@router.get("/{case_id}")
async def get_case(case_id: str, request: Request):
    """
    Get full case details including history and checklist.
    Helpers can only access their assigned cases.
    """
    user = get_current_user(request)
    db = await get_db()
    
    # Get case
    cases_col = db['scs_cases']
    case = await cases_col.find_one({"case_id": case_id})
    
    if not case:
        raise HTTPException(404, {"error": "Case not found", "case_id": case_id})
    
    # Access control: helpers can only see their assigned cases
    if user.is_helper and case.get("assigned_to") != user.user_id:
        raise HTTPException(
            403,
            {
                "error": "ACCESS_DENIED",
                "message": "This case is not assigned to you",
                "case_id": case_id
            }
        )
    
    # Serialize the case
    case_data = serialize_doc(case)
    
    # Get case history (risk progression)
    history_col = db['scs_case_history']
    history_cursor = history_col.find({"case_id": case_id}).sort("ingestion_date", 1)
    history = []
    async for doc in history_cursor:
        history.append(serialize_doc(doc))
    
    # Get checklist items
    checklist_col = db['scs_checklist']
    checklist_cursor = checklist_col.find({"case_id": case_id}).sort("display_order", 1)
    checklist = []
    async for doc in checklist_cursor:
        checklist.append(serialize_doc(doc))
    
    # Get review requests (if any)
    review_col = db['scs_review_requests']
    review_cursor = review_col.find({"case_id": case_id})
    reviews = []
    async for doc in review_cursor:
        reviews.append(serialize_doc(doc))
    
    # Get reassignment requests (if any)
    reassign_col = db['scs_reassignment_requests']
    reassign_cursor = reassign_col.find({"case_id": case_id})
    reassignments = []
    async for doc in reassign_cursor:
        reassignments.append(serialize_doc(doc))
    
    # Audit the view
    await _audit(db, user, "VIEW_CASE", case_id)
    
    # Combine all data
    case_data["history"] = history
    case_data["checklist"] = checklist
    case_data["review_requests"] = reviews
    case_data["reassignment_requests"] = reassignments
    
    return case_data


# ─── Assign case to helper (admin only) ───────────────────────────────────────
@router.post("/{case_id}/assign")
async def assign_case(
    case_id: str,
    request: Request,
    assignment: CaseAssignment = Body(...)
):
    """Assign a case to a youth helper (admin only)"""
    user = await require_admin(request)
    db = await get_db()
    
    cases_col = db['scs_cases']
    users_col = db['scs_users']
    
    # Verify case exists
    case = await cases_col.find_one({"case_id": case_id})
    if not case:
        raise HTTPException(404, {"error": "Case not found"})
    
    # Verify helper exists
    helper = await users_col.find_one({"user_id": assignment.assigned_to})
    if not helper:
        raise HTTPException(404, {"error": "Helper not found"})
    
    if helper.get("role") != "youth_helper":
        raise HTTPException(400, {"error": "Can only assign to youth helpers"})
    
    # Update case
    result = await cases_col.update_one(
        {"case_id": case_id},
        {
            "$set": {
                "assigned_to": assignment.assigned_to,
                "case_status": "assigned",
                "updated_at": datetime.now()
            }
        }
    )
    
    if result.modified_count == 0:
        raise HTTPException(500, {"error": "Failed to assign case"})
    
    # Audit
    await _audit(db, user, "ASSIGN_CASE", case_id, {
        "assigned_to": assignment.assigned_to
    })
    
    # Return updated case
    updated_case = await cases_col.find_one({"case_id": case_id})
    return serialize_doc(updated_case)


# ─── Update case (work status, priority, etc.) ────────────────────────────────
@router.patch("/{case_id}")
async def update_case(
    case_id: str,
    request: Request,
    update: CaseUpdate = Body(...)
):
    """
    Update case fields (work_status, priority, etc.).
    Helpers can only update their assigned cases.
    """
    user = get_current_user(request)
    db = await get_db()
    
    cases_col = db['scs_cases']
    
    # Verify case exists and access
    case = await cases_col.find_one({"case_id": case_id})
    if not case:
        raise HTTPException(404, {"error": "Case not found"})
    
    # Access control
    if user.is_helper and case.get("assigned_to") != user.user_id:
        raise HTTPException(403, {"error": "Not authorized to update this case"})
    
    # Build update document
    update_doc = {"updated_at": datetime.now()}
    if update.work_status:
        update_doc["work_status"] = update.work_status
    if update.priority:
        update_doc["priority"] = update.priority
    if update.case_status:
        update_doc["case_status"] = update.case_status
    
    # Update case
    result = await cases_col.update_one(
        {"case_id": case_id},
        {"$set": update_doc}
    )
    
    if result.modified_count == 0:
        raise HTTPException(500, {"error": "Failed to update case"})
    
    # Audit
    await _audit(db, user, "UPDATE_CASE", case_id, update_doc)
    
    # Return updated case
    updated_case = await cases_col.find_one({"case_id": case_id})
    return serialize_doc(updated_case)


# ─── Get cases by priority (dashboard stats) ──────────────────────────────────
@router.get("/stats/by-priority")
async def get_cases_by_priority(request: Request):
    """Get case counts grouped by priority"""
    user = get_current_user(request)
    db = await get_db()
    cases_col = db['scs_cases']
    
    # Build base query (helpers only see their cases)
    match_stage = {}
    if user.is_helper:
        match_stage["assigned_to"] = user.user_id
    
    pipeline = [
        {"$match": match_stage},
        {"$group": {
            "_id": "$priority",
            "count": {"$sum": 1}
        }}
    ]
    
    cursor = cases_col.aggregate(pipeline)
    stats = {}
    async for doc in cursor:
        priority = doc["_id"] or "unknown"
        stats[priority] = doc["count"]
    
    return stats


# ─── Get cases by category (dashboard stats) ──────────────────────────────────
@router.get("/stats/by-category")
async def get_cases_by_category(request: Request):
    """Get case counts grouped by category"""
    user = get_current_user(request)
    db = await get_db()
    cases_col = db['scs_cases']
    
    # Build base query
    match_stage = {}
    if user.is_helper:
        match_stage["assigned_to"] = user.user_id
    
    pipeline = [
        {"$match": match_stage},
        {"$group": {
            "_id": "$category",
            "count": {"$sum": 1},
            "avg_risk": {"$avg": "$current_risk_score"}
        }},
        {"$sort": {"count": -1}}
    ]
    
    cursor = cases_col.aggregate(pipeline)
    stats = []
    async for doc in cursor:
        stats.append({
            "category": doc["_id"],
            "count": doc["count"],
            "avg_risk": round(doc["avg_risk"], 2) if doc["avg_risk"] else 0
        })
    
    return stats
