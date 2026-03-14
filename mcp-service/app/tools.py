"""
MCP Tools for SCS Case Management - MongoDB Version
Provides tools for reading and writing case data with MongoDB backend.
"""
import httpx
import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import HTTPException
from .database import get_db, get_next_id, serialize_doc
from .auth import AuthUser
from .config import settings


def _now_iso() -> str:
    """Return current time as ISO 8601 string"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hours_from_now_iso(hours: int) -> str:
    """Return time N hours from now as ISO 8601 string"""
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


async def audit_log(
    tool_name: str,
    actor_id: str,
    actor_role: str,
    payload: dict,
    result: dict,
    *,
    request_id: str = "",
    case_id: str = "",
    approved_plan_hash: str = "",
):
    """Log tool usage in MongoDB audit collection"""
    db = await get_db()
    audit_col = db['mcp_audit_log']
    
    await audit_col.insert_one({
        "tool_name": tool_name,
        "actor_id": actor_id,
        "actor_role": actor_role,
        "payload": json.dumps(payload),
        "result": json.dumps(result),
        "request_id": request_id,
        "case_id": case_id,
        "approved_plan_hash": approved_plan_hash,
        "created_at": _now_iso(),
    })


async def _assert_case_write_access(db, case_id: str, user: AuthUser):
    """Validate user can write to this case"""
    cases_col = db['scs_cases']
    case = await cases_col.find_one({"case_id": case_id})
    
    if not case:
        raise HTTPException(404, "Case not found")
    if user.is_helper and case.get("assigned_to") != user.user_id:
        raise HTTPException(403, "Not your assigned case")


# ─── READ TOOLS (No approval needed) ─────────────────────────────────────────

async def tool_get_case(case_id: str, user: AuthUser) -> dict:
    """Get full case details including checklist and history"""
    db = await get_db()
    cases_col = db['scs_cases']
    
    case = await cases_col.find_one({"case_id": case_id})
    if not case:
        raise HTTPException(404, "Case not found")
    
    if user.is_helper and case.get("assigned_to") != user.user_id:
        raise HTTPException(403, "Not your assigned case")
    
    # Get checklist items
    checklist_col = db['scs_checklist']
    checklist_items = await checklist_col.find({"case_id": case_id}).sort("display_order", 1).to_list(length=None)
    
    case_data = serialize_doc(case)
    case_data["checklist"] = [serialize_doc(item) for item in checklist_items]
    
    await audit_log(
        "get_case", user.user_id, user.role,
        {"case_id": case_id}, {"found": True},
        case_id=case_id
    )
    return case_data


async def tool_list_cases_summary(
    user: AuthUser,
    category: Optional[str] = None,
    status: Optional[str] = None,
) -> list[dict]:
    """List cases (admins see all, helpers see only assigned)"""
    db = await get_db()
    cases_col = db['scs_cases']
    
    query = {}
    if user.is_helper:
        query["assigned_to"] = user.user_id
    if category:
        query["current_category"] = category
    if status:
        query["status"] = status
    
    cases = await cases_col.find(query).sort([
        ("current_risk_score", -1),
        ("created_at", -1)
    ]).to_list(length=None)
    
    result = [serialize_doc(case) for case in cases]
    await audit_log(
        "list_cases_summary", user.user_id, user.role,
        {"category": category, "status": status}, {"count": len(result)}
    )
    return result


async def tool_list_assigned_cases(user: AuthUser) -> list[dict]:
    """Get all cases assigned to the user"""
    db = await get_db()
    cases_col = db['scs_cases']
    
    cases = await cases_col.find({"assigned_to": user.user_id}).sort("current_risk_score", -1).to_list(length=None)
    
    result = [serialize_doc(case) for case in cases]
    await audit_log("list_assigned_cases", user.user_id, user.role, {}, {"count": len(result)})
    return result


async def tool_get_case_history(case_id: str, user: AuthUser) -> list[dict]:
    """Get case risk score history"""
    db = await get_db()
    cases_col = db['scs_cases']
    
    case = await cases_col.find_one({"case_id": case_id})
    if not case:
        raise HTTPException(404, "Case not found")
    if user.is_helper and case.get("assigned_to") != user.user_id:
        raise HTTPException(403, "Not your assigned case")
    
    history_col = db['scs_case_history']
    history = await history_col.find({"case_id": case_id}).sort("timestamp", 1).to_list(length=None)
    
    result = [serialize_doc(h) for h in history]
    await audit_log("get_case_history", user.user_id, user.role,
                    {"case_id": case_id}, {"rows": len(result)},
                    case_id=case_id)
    return result


async def tool_search_protocol(query: str, user: AuthUser) -> dict:
    """Delegates to chatbot-service RAG search"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.chatbot_service_url}/chat",
                json={"message": f"Protocol search: {query}"},
                headers={"X-User-Id": user.user_id, "X-User-Role": user.role},
            )
        result = resp.json()
    except Exception as e:
        result = {"response": f"Protocol search unavailable: {e}", "tool_calls": []}
    
    await audit_log("search_protocol", user.user_id, user.role, {"query": query}, {"found": True})
    return result


async def tool_get_similar_cases(case_id: str, user: AuthUser, top_k: int = 5) -> dict:
    """Delegates to chatbot-service similarity endpoint"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.chatbot_service_url}/similar-cases/{case_id}",
                params={"top_k": top_k},
            )
        result = resp.json()
    except Exception as e:
        result = {"case_id": case_id, "similar_cases": [], "error": str(e)}
    
    await audit_log("get_similar_cases", user.user_id, user.role,
                    {"case_id": case_id}, result,
                    case_id=case_id)
    return result


# ─── WRITE TOOLS (Approval-gated) ────────────────────────────────────────────

async def tool_add_checklist_item(
    case_id: str,
    label: str,
    user: AuthUser,
    is_mandatory: bool = False,
    *,
    request_id: str = "",
    approved_plan_hash: str = "",
) -> dict:
    """Add a new checklist item to a case"""
    db = await get_db() 
    await _assert_case_write_access(db, case_id, user)
    
    checklist_col = db['scs_checklist']
    
    # Get next checklist_item_id
    new_id = await get_next_id('scs_checklist', 'checklist_item_id')
    
    # Get max display_order for this case
    max_order_doc = await checklist_col.find_one(
        {"case_id": case_id},
        sort=[("display_order", -1)]
    )
    display_order = (max_order_doc.get("display_order", 0) + 1) if max_order_doc else 1
    
    checklist_item = {
        "checklist_item_id": new_id,
        "case_id": case_id,
        "template_id": None,  # Custom item, not from template
        "label": label,
        "is_mandatory": is_mandatory,
        "completed": False,
        "comments": [],
        "completed_at": None,
        "completed_by": None,
        "display_order": display_order,
        "created_at": datetime.now(timezone.utc),
        "created_by": "agent"
    }
    
    await checklist_col.insert_one(checklist_item)
    
    result = {"checklist_item_id": new_id, "label": label, "case_id": case_id}
    await audit_log(
        "add_checklist_item", user.user_id, user.role,
        {"case_id": case_id, "label": label, "is_mandatory": is_mandatory},
        result,
        request_id=request_id, case_id=case_id, approved_plan_hash=approved_plan_hash,
    )
    return result


async def tool_add_checklist_items(
    case_id: str,
    items: list[dict],
    user: AuthUser,
    *,
    request_id: str = "",
    approved_plan_hash: str = "",
) -> dict:
    """Add multiple checklist items to a case (bulk operation)"""
    db = await get_db()
    await _assert_case_write_access(db, case_id, user)
    
    checklist_col = db['scs_checklist']
    
    # Get max display_order for this case
    max_order_doc = await checklist_col.find_one(
        {"case_id": case_id},
        sort=[("display_order", -1)]
    )
    display_order = (max_order_doc.get("display_order", 0) + 1) if max_order_doc else 1
    
    results = []
    for item in items:
        label = item.get("label", "")
        if not label:
            results.append({
                "success": False,
                "error": "Label is required",
                "label": label
            })
            continue
        
        is_mandatory = item.get("is_mandatory", False)
        
        # Get next checklist_item_id
        new_id = await get_next_id('scs_checklist', 'checklist_item_id')
        
        checklist_item = {
            "checklist_item_id": new_id,
            "case_id": case_id,
            "template_id": None,
            "label": label,
            "is_mandatory": is_mandatory,
            "completed": False,
            "comments": [],
            "completed_at": None,
            "completed_by": None,
            "display_order": display_order,
            "created_at": datetime.now(timezone.utc),
            "created_by": "agent"
        }
        
        try:
            await checklist_col.insert_one(checklist_item)
            results.append({
                "success": True,
                "checklist_item_id": new_id,
                "label": label,
                "is_mandatory": is_mandatory,
                "display_order": display_order
            })
            display_order += 1
        except Exception as e:
            results.append({
                "success": False,
                "error": str(e),
                "label": label
            })
    
    result = {
        "case_id": case_id,
        "total_items": len(items),
        "successful": sum(1 for r in results if r.get("success")),
        "failed": sum(1 for r in results if not r.get("success")),
        "results": results
    }
    
    await audit_log(
        "add_checklist_items", user.user_id, user.role,
        {"case_id": case_id, "item_count": len(items)},
        result,
        request_id=request_id, case_id=case_id, approved_plan_hash=approved_plan_hash,
    )
    return result


async def tool_update_checklist_item_status(
    case_id: str,
    checklist_item_id: int,
    completed: bool,
    comment: str,
    user: AuthUser,
    *,
    request_id: str = "",
    approved_plan_hash: str = "",
) -> dict:
    """Update checklist item completion status"""
    if not comment:
        raise HTTPException(400, "comment required for status change")
    
    db = await get_db()
    await _assert_case_write_access(db, case_id, user)
    
    checklist_col = db['scs_checklist']
    
    # Verify item exists
    item = await checklist_col.find_one({"checklist_item_id": checklist_item_id, "case_id": case_id})
    if not item:
        raise HTTPException(404, "Checklist item not found")
    
    # Update item
    update_data = {
        "completed": completed,
        "completed_at": datetime.now(timezone.utc) if completed else None,
        "completed_by": user.user_id if completed else None
    }
    
    # Add comment
    await checklist_col.update_one(
        {"checklist_item_id": checklist_item_id},
        {
            "$set": update_data,
            "$push": {
                "comments": {
                    "author_id": user.user_id,
                    "content": comment,
                    "created_at": _now_iso()
                }
            }
        }
    )
    
    result = {"checklist_item_id": checklist_item_id, "completed": completed, "comment_saved": True}
    await audit_log(
        "update_checklist_item_status", user.user_id, user.role,
        {"case_id": case_id, "checklist_item_id": checklist_item_id, "completed": completed, "comment": comment[:80]},
        result,
        request_id=request_id, case_id=case_id, approved_plan_hash=approved_plan_hash,
    )
    return result


async def tool_request_reassignment(
    case_id: str,
    reason: str,
    user: AuthUser,
    requested_to: Optional[str] = None,
    *,
    request_id: str = "",
    approved_plan_hash: str = "",
) -> dict:
    """Submit a case reassignment request"""
    db = await get_db()
    cases_col = db['scs_cases']
    
    case = await cases_col.find_one({"case_id": case_id})
    if not case:
        raise HTTPException(404, "Case not found")
    if user.is_helper and case.get("assigned_to") != user.user_id:
        raise HTTPException(403, "Not your case")
    
    reassign_col = db['scs_reassignment_requests']
    
    # Get next request ID
    req_id = await get_next_id('scs_reassignment_requests', 'request_id')
    
    reassignment_request = {
        "request_id": req_id,
        "case_id": case_id,
        "requested_by": user.user_id,
        "requested_to": requested_to,
        "reason": reason,
        "status": "pending",
        "reviewed_by": None,
        "reviewed_at": None,
        "created_at": datetime.now(timezone.utc)
    }
    
    await reassign_col.insert_one(reassignment_request)
    
    result = {"request_id": req_id, "case_id": case_id, "status": "pending"}
    await audit_log(
        "request_reassignment", user.user_id, user.role,
        {"case_id": case_id, "reason": reason[:100], "requested_to": requested_to},
        result,
        request_id=request_id, case_id=case_id, approved_plan_hash=approved_plan_hash,
    )
    return result


async def tool_submit_review_request(
    case_id: str,
    review_type: str,
    reason: str,
    user: AuthUser,
    *,
    request_id: str = "",
    approved_plan_hash: str = "",
) -> dict:
    """Submit a case for review (escalation, closure, etc.)"""
    valid_types = {"escalation", "closure", "follow_up", "general"}
    if review_type not in valid_types:
        raise HTTPException(400, f"review_type must be one of {valid_types}")
    
    db = await get_db()
    await _assert_case_write_access(db, case_id, user)
    
    review_col = db['scs_review_requests']
    
    # Get next review request ID
    req_id = await get_next_id('scs_review_requests', 'request_id')
    
    review_request = {
        "request_id": req_id,
        "case_id": case_id,
        "requested_by": user.user_id,
        "review_type": review_type,
        "reason": reason,
        "status": "pending",
        "reviewed_by": None,
        "reviewed_at": None,
        "resolution": None,
        "created_at": datetime.now(timezone.utc)
    }
    
    await review_col.insert_one(review_request)
    
    # Update case status to indicate review needed
    cases_col = db['scs_cases']
    await cases_col.update_one(
        {"case_id": case_id},
        {"$set": {"status": "in_review", "updated_at": datetime.now(timezone.utc)}}
    )
    
    result = {"request_id": req_id, "case_id": case_id, "review_type": review_type, "status": "pending"}
    await audit_log(
        "submit_review_request", user.user_id, user.role,
        {"case_id": case_id, "review_type": review_type, "reason": reason[:100]},
        result,
        request_id=request_id, case_id=case_id, approved_plan_hash=approved_plan_hash,
    )
    return result


async def tool_add_case_note(
    case_id: str,
    content: str,
    user: AuthUser,
    note_type: str = "general",
    *,
    request_id: str = "",
    approved_plan_hash: str = "",
) -> dict:
    """Add a note to a case"""
    db = await get_db()
    await _assert_case_write_access(db, case_id, user)
    
    cases_col = db['scs_cases']
    tagged_content = f"[{note_type.upper()}] {content}" if note_type != "general" else content
    
    await cases_col.update_one(
        {"case_id": case_id},
        {
            "$push": {
                "notes": {
                    "author_id": user.user_id,
                    "content": tagged_content,
                    "note_type": note_type,
                    "created_at": _now_iso()
                }
            },
            "$set": {"updated_at": datetime.now(timezone.utc)}
        }
    )
    
    result = {"case_id": case_id, "note_type": note_type, "saved": True}
    await audit_log(
        "add_case_note", user.user_id, user.role,
        {"case_id": case_id, "note_type": note_type, "content_len": len(content)},
        result,
        request_id=request_id, case_id=case_id, approved_plan_hash=approved_plan_hash,
    )
    return result


async def tool_update_case_status(
    case_id: str,
    status: str,
    user: AuthUser,
    *,
    request_id: str = "",
    approved_plan_hash: str = "",
) -> dict:
    """Update case status"""
    valid = {"new", "in_progress", "in_review", "outreach", "followup", "completed", "closed"}
    if status not in valid:
        raise HTTPException(400, f"Invalid status: {status}")
    
    db = await get_db()
    await _assert_case_write_access(db, case_id, user)
    
    cases_col = db['scs_cases']
    await cases_col.update_one(
        {"case_id": case_id},
        {"$set": {"status": status, "updated_at": datetime.now(timezone.utc)}}
    )
    
    result = {"case_id": case_id, "status": status}
    await audit_log(
        "update_case_status", user.user_id, user.role,
        {"case_id": case_id, "status": status},
        result,
        request_id=request_id, case_id=case_id, approved_plan_hash=approved_plan_hash,
    )
    return result
