"""
MongoDB-based case management routes for SCS Youth Helper Dashboard
"""
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Request, Body
from pydantic import BaseModel
from ..database import get_db, serialize_doc, get_next_id
from ..auth import get_current_user, require_admin, AuthUser

router = APIRouter(prefix="/cases", tags=["cases"])


# ─── Pydantic Models ──────────────────────────────────────────────────────────

class CaseAssignment(BaseModel):
    assigned_to: str


class CaseUpdate(BaseModel):
    work_status: Optional[str] = None
    priority: Optional[str] = None
    case_status: Optional[str] = None


class ReviewRequest(BaseModel):
    reason: str


class ReviewResponse(BaseModel):
    admin_comment: str
    approach: Optional[str] = None


class ReassignmentRequest(BaseModel):
    reason: str
    requested_to: Optional[str] = None  # Preferred new assignee


class ReassignmentReview(BaseModel):
    status: str  # "approved" | "declined"
    review_notes: str
    new_assigned_to: Optional[str] = None  # Required if approved


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


# ─── Get cases that need review (admin only) ──────────────────────────────────
@router.get("/needs-review")
async def get_cases_needing_review(request: Request):
    """Get all cases with pending review requests (admin only)"""
    user = await require_admin(request)
    db = await get_db()
    
    review_col = db['scs_review_requests']
    cases_col = db['scs_cases']
    
    # Find all pending reviews
    cursor = review_col.find({"request_status": "pending"})
    
    cases_needing_review = []
    async for review_doc in cursor:
        case = await cases_col.find_one({"case_id": review_doc["case_id"]})
        if case:
            case_data = serialize_doc(case)
            case_data["review_request"] = serialize_doc(review_doc)
            cases_needing_review.append(case_data)
    
    return cases_needing_review


# ─── Get reassignment requests (admin) ─────────────────────────────────────────
@router.get("/reassignment-requests")
async def get_reassignment_requests(
    request: Request,
    status: Optional[str] = None
):
    """Get all reassignment requests (admin only), optionally filtered by status"""
    user = get_current_user(request)
    require_admin(user)
    
    db = await get_db()
    reassign_col = db['scs_reassignment_requests']
    
    # Build query
    query = {}
    if status:
        query["request_status"] = status
    
    cursor = reassign_col.find(query).sort("requested_at", -1)
    requests = []
    
    async for doc in cursor:
        # Get case details
        cases_col = db['scs_cases']
        case = await cases_col.find_one({"case_id": doc["case_id"]})
        
        req_data = serialize_doc(doc)
        if case:
            req_data["case"] = serialize_doc(case)
        
        requests.append(req_data)
    
    return requests


# ─── Review reassignment request (admin) ───────────────────────────────────────
@router.post("/reassignment-requests/{request_id}/review")
async def review_reassignment_request(
    request_id: int,
    request: Request,
    review: ReassignmentReview = Body(...)
):
    """
    Admin reviews and approves/declines a reassignment request.
    If approved, the case is reassigned to the new helper.
    """
    user = get_current_user(request)
    require_admin(user)
    
    db = await get_db()
    reassign_col = db['scs_reassignment_requests']
    
    # Find the request
    reassign_req = await reassign_col.find_one({"request_id": request_id})
    if not reassign_req:
        raise HTTPException(404, {"error": "Reassignment request not found"})
    
    if reassign_req["request_status"] != "pending":
        raise HTTPException(400, {"error": "Request already processed"})
    
    # For approval, use new_assigned_to if provided, otherwise default to suggested_helper
    final_assignee = review.new_assigned_to
    if review.status == "approved":
        if not final_assignee:
            final_assignee = reassign_req.get("suggested_helper")
        if not final_assignee:
            raise HTTPException(400, {"error": "Cannot approve: no helper specified in request or review"})
    
    # Update reassignment request
    await reassign_col.update_one(
        {"request_id": request_id},
        {
            "$set": {
                "request_status": review.status,
                "reviewed_by": user.user_id,
                "reviewed_at": _now_iso(),
                "new_assigned_to": final_assignee if review.status == "approved" else None,
                "review_notes": review.review_notes,
                "updated_at": _now_iso()
            }
        }
    )
    
    # If approved, update the case assignment and reset work_status
    cases_col = db['scs_cases']
    if review.status == "approved":
        await cases_col.update_one(
            {"case_id": reassign_req["case_id"]},
            {
                "$set": {
                    "assigned_to": final_assignee,
                    "case_status": "assigned",
                    "work_status": "not_started",
                    "updated_at": datetime.now()
                }
            }
        )
        
        # Add history entry
        history_col = db['scs_case_history']
        history_doc = {
            "case_id": reassign_req["case_id"],
            "action": "reassigned",
            "performed_by": user.user_id,
            "reason": f"Reassignment approved: {review.review_notes}",
            "timestamp": _now_iso(),
            "old_value": reassign_req["current_assigned_to"],
            "new_value": final_assignee
        }
        await history_col.insert_one(history_doc)
    else:
        # Declined - revert case status to assigned
        await cases_col.update_one(
            {"case_id": reassign_req["case_id"]},
            {
                "$set": {
                    "case_status": "assigned",
                    "updated_at": datetime.now()
                }
            }
        )
    
    # Audit
    await _audit(db, user, "REVIEW_REASSIGNMENT", reassign_req["case_id"], {
        "request_id": request_id,
        "status": review.status,
        "new_assigned_to": final_assignee if review.status == "approved" else None,
        "review_notes": review.review_notes
    })
    
    return {
        "status": "success",
        "message": f"Reassignment request {review.status}",
        "case_id": reassign_req["case_id"]
    }


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


# ─── Submit case for review (helper) ──────────────────────────────────────────
@router.post("/{case_id}/review-request")
async def create_review_request(
    case_id: str,
    request: Request,
    review_req: ReviewRequest = Body(...)
):
    """
    Submit a case for admin review with a reason.
    Helper must be assigned to the case.
    """
    user = get_current_user(request)
    db = await get_db()
    
    # Verify case exists and access
    cases_col = db['scs_cases']
    case = await cases_col.find_one({"case_id": case_id})
    if not case:
        raise HTTPException(404, {"error": "Case not found"})
    
    if user.is_helper and case.get("assigned_to") != user.user_id:
        raise HTTPException(403, {"error": "Not authorized - case not assigned to you"})
    
    # Create review request
    review_col = db['scs_review_requests']
    
    # Check if already has pending review
    existing = await review_col.find_one({
        "case_id": case_id,
        "request_status": "pending"
    })
    if existing:
        raise HTTPException(400, {"error": "Review request already pending for this case"})
    
    review_doc = {
        "case_id": case_id,
        "requested_by": user.user_id,
        "reason": review_req.reason,
        "request_status": "pending",
        "resolution_notes": None,
        "resolved_by": None,
        "created_at": _now_iso(),
        "resolved_at": None,
        "updated_at": _now_iso()
    }
    
    await review_col.insert_one(review_doc)
    
    # Update case work_status to "to_review"
    await cases_col.update_one(
        {"case_id": case_id},
        {
            "$set": {
                "work_status": "to_review",
                "updated_at": datetime.now()
            }
        }
    )
    
    # Audit
    await _audit(db, user, "REQUEST_REVIEW", case_id, {"reason": review_req.reason})
    
    return {"status": "success", "message": "Review request submitted"}


# ─── Complete review (admin only) ─────────────────────────────────────────────
@router.post("/{case_id}/complete-review")
async def complete_review(
    case_id: str,
    request: Request,
    review_response: ReviewResponse = Body(...)
):
    """
    Admin completes a review with comments and approach.
    Updates case work_status back to "in_progress" and marks review as completed.
    """
    user = await require_admin(request)
    db = await get_db()
    
    # Find pending review request
    review_col = db['scs_review_requests']
    review = await review_col.find_one({
        "case_id": case_id,
        "request_status": "pending"
    })
    
    if not review:
        raise HTTPException(404, {"error": "No pending review request found for this case"})
    
    # Combine approach and comments for resolution_notes
    resolution_text = ""
    if review_response.approach:
        resolution_text += f"**Approach:** {review_response.approach}\n\n"
    if review_response.admin_comment:
        resolution_text += f"**Comments:** {review_response.admin_comment}"
    
    # Fallback to just comment or approach if only one is provided
    if not resolution_text:
        resolution_text = review_response.approach or review_response.admin_comment or ""
    
    # Update review request (only resolution_notes field exists in DB)
    await review_col.update_one(
        {"_id": review["_id"]},
        {
            "$set": {
                "request_status": "resolved",
                "resolution_notes": resolution_text.strip(),
                "resolved_by": user.user_id,
                "resolved_at": _now_iso(),
                "updated_at": _now_iso()
            }
        }
    )
    
    # Update case work_status back to "in_progress"
    cases_col = db['scs_cases']
    await cases_col.update_one(
        {"case_id": case_id},
        {
            "$set": {
                "work_status": "in_progress",
                "updated_at": datetime.now()
            }
        }
    )
    
    # Audit
    await _audit(db, user, "COMPLETE_REVIEW", case_id, {
        "admin_comment": review_response.admin_comment,
        "approach": review_response.approach
    })
    
    return {"status": "success", "message": "Review completed"}


# ─── Submit reassignment request (helper) ──────────────────────────────────────
@router.post("/{case_id}/reassignment-request")
async def create_reassignment_request(
    case_id: str,
    request: Request,
    reassign_req: ReassignmentRequest = Body(...)
):
    """
    Submit a case reassignment request.
    Helper must be assigned to the case.
    """
    user = get_current_user(request)
    db = await get_db()
    
    # Verify case exists and access
    cases_col = db['scs_cases']
    case = await cases_col.find_one({"case_id": case_id})
    if not case:
        raise HTTPException(404, {"error": "Case not found"})
    
    if user.is_helper and case.get("assigned_to") != user.user_id:
        raise HTTPException(403, {"error": "Not authorized - case not assigned to you"})
    
    # Create reassignment request
    reassign_col = db['scs_reassignment_requests']
    
    # Check if already has pending reassignment
    existing = await reassign_col.find_one({
        "case_id": case_id,
        "request_status": "pending"
    })
    if existing:
        raise HTTPException(400, {"error": "Reassignment request already pending for this case"})
    
    # Get next request_id
    request_id = await get_next_id('scs_reassignment_requests', 'request_id')
    
    reassign_doc = {
        "request_id": request_id,
        "case_id": case_id,
        "requested_by": user.user_id,
        "current_assigned_to": case.get("assigned_to"),
        "reason": reassign_req.reason,
        "suggested_helper": reassign_req.requested_to,
        "request_status": "pending",
        "requested_at": _now_iso(),
        "reviewed_by": None,
        "reviewed_at": None,
        "new_assigned_to": None,
        "review_notes": None,
        "created_at": _now_iso(),
        "updated_at": _now_iso()
    }
    
    await reassign_col.insert_one(reassign_doc)
    
    # Update case status to "reassigned" (pending reassignment)
    await cases_col.update_one(
        {"case_id": case_id},
        {
            "$set": {
                "case_status": "reassigned",
                "updated_at": datetime.now()
            }
        }
    )
    
    # Audit
    await _audit(db, user, "REQUEST_REASSIGNMENT", case_id, {
        "reason": reassign_req.reason,
        "requested_to": reassign_req.requested_to
    })
    
    return {"status": "success", "message": "Reassignment request submitted"}


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
