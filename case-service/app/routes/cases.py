import json
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Request, params
from ..database import get_db, serialize_doc
from ..auth import get_current_user, require_admin, AuthUser

router = APIRouter(prefix="/cases", tags=["cases"])


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _audit(db, actor: AuthUser, action: str, resource: str, detail: dict | None = None):
    """Write an immutable audit record."""
    audit_col = db['scs_audit_log']
    await audit_col.insert_one({
        "actor_id": actor.user_id,
        "actor_role": actor.role,
        "action": action,
        "resource": resource,
        "detail": detail,
        "created_at": _now_iso()
    })


async def _record_status_change(db, case_id: str, field: str, old_value, new_value, actor: AuthUser, reason: str | None = None):
    """Record a status change in the status_history table."""
    status_history_col = db['scs_status_history']
    await status_history_col.insert_one({
        "case_id": case_id,
        "field": field,
        "old_value": old_value,
        "new_value": new_value,
        "reason": reason,
        "actor_id": actor.user_id,
        "actor_role": actor.role,
        "created_at": _now_iso()
    })


async def _assert_case_access(db, case_id: str, user: AuthUser):
    """Strict access check — helpers only see their assigned cases."""
    cases_col = db['scs_cases']
    case = await cases_col.find_one({"case_id": case_id})
    
    if not case:
        raise HTTPException(404, "Case not found")
    
    if user.is_helper and case.get("assigned_to") != user.user_id:
        raise HTTPException(
            403,
            {
                "code": "ACCESS_DENIED",
                "message": "This case is not assigned to you. Access denied.",
            },
        )
    return case


# ─── List cases (summary) ─────────────────────────────────────────────────────
@router.get("/summary")
async def list_cases_summary(
    request: Request,
    category: Optional[str] = None,
    status: Optional[str] = None,
    case_status: Optional[str] = None,
    work_status: Optional[str] = None,
    assigned_to: Optional[str] = None,
):
    user = get_current_user(request)
    db = await get_db()
    cases_col = db['scs_cases']

    # Helpers only see their own assigned cases in summary lists
    if user.is_helper:
        assigned_to = user.user_id

    # Build MongoDB query filter
    query_filter = {}
    if category:
        query_filter["category"] = category
    if status:
        query_filter["status"] = status
    if case_status:
        query += " AND case_status = ?"
        params.append(case_status)
    if work_status:
        query += " AND work_status = ?"
        params.append(work_status)
    if assigned_to:
        query += " AND assigned_to = ?"
        params.append(assigned_to)
    query += " ORDER BY risk_score DESC, created_at DESC"

    async with db.execute(query, params) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


# ─── Assigned cases (helper's own — full detail) ──────────────────────────────
@router.get("/assigned")
async def list_assigned_cases(request: Request):
    user = get_current_user(request)
    db = await get_db()
    async with db.execute(
        """
        SELECT case_id, user_id, assigned_to, risk_score, category,
               explanation_signals, case_status, work_status, status,
               priority, needs_review, created_at, last_signal_at
        FROM cases WHERE assigned_to = ?
        ORDER BY risk_score DESC, created_at DESC
        """,
        (user.user_id,),
    ) as cur:
        rows = await cur.fetchall()
    return [_row_to_dict(r) for r in rows]


# ─── Needs Review (admin + helpers for own cases) ─────────────────────────────
@router.get("/needs-review")
async def list_needs_review(request: Request):
    user = get_current_user(request)
    db = await get_db()
    if user.is_helper:
        async with db.execute(
            """SELECT * FROM cases WHERE needs_review = 1 AND assigned_to = ?
               ORDER BY risk_score DESC""",
            (user.user_id,),
        ) as cur:
            rows = await cur.fetchall()
    else:
        async with db.execute(
            "SELECT * FROM cases WHERE needs_review = 1 ORDER BY risk_score DESC",
        ) as cur:
            rows = await cur.fetchall()
    return [_row_to_dict(r) for r in rows]


# ─── Unassigned cases (admin only) ───────────────────────────────────────────
@router.get("/unassigned")
async def list_unassigned(request: Request):
    user = await require_admin(request)
    db = await get_db()
    async with db.execute(
        """SELECT case_id, user_id, assigned_to, risk_score, category,
                  case_status, work_status, status, priority, needs_review,
                  created_at, last_signal_at
           FROM cases WHERE assigned_to IS NULL OR case_status = 'unassigned'
           ORDER BY risk_score DESC, created_at DESC"""
    ) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


# ─── Get single case (full detail + strict RBAC) ─────────────────────────────
@router.get("/{case_id}")
async def get_case(case_id: str, request: Request):
    user = get_current_user(request)
    db = await get_db()

    async with db.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Case not found")

    case = _row_to_dict(row)

    # ── Strict access control for helpers ──────────────────────────────────
    if user.is_helper and case.get("assigned_to") != user.user_id:
        raise HTTPException(
            403,
            {
                "code": "ACCESS_DENIED",
                "message": "This case is not assigned to you. Access denied.",
                "case_id": case_id,
            },
        )

    # Audit the view
    await _audit(db, user, "VIEW_CASE", case_id)
    await db.commit()

    # Attach checklist
    async with db.execute(
        "SELECT * FROM checklist_items WHERE case_id = ? ORDER BY COALESCE(parent_id, id), id",
        (case_id,),
    ) as cur:
        checklist = [dict(r) for r in await cur.fetchall()]

    # Attach pending reassignment requests
    async with db.execute(
        "SELECT * FROM reassignment_requests WHERE case_id = ? AND status='pending'",
        (case_id,),
    ) as cur:
        reassigns = [dict(r) for r in await cur.fetchall()]

    case["checklist"] = checklist
    case["pending_reassignments"] = reassigns
    return case


# ─── Full timeline (case events in chronological order) ──────────────────────
@router.get("/{case_id}/timeline")
async def get_case_timeline(case_id: str, request: Request):
    """
    Returns a unified, chronologically ordered timeline of all events:
    ingestion history, status changes, checklist activity, escalation records,
    reassignment logs, case notes, and audit highlights.
    """
    user = get_current_user(request)
    db = await get_db()
    await _assert_case_access(db, case_id, user)

    events: list[dict] = []

    # Ingestion history
    async with db.execute(
        """SELECT id, risk_score, category, explanation_snapshot,
                  frequency_metrics, action_taken, escalation_flag, timestamp
           FROM case_history WHERE case_id = ? ORDER BY timestamp ASC""",
        (case_id,),
    ) as cur:
        for r in await cur.fetchall():
            d = dict(r)
            for f in ("explanation_snapshot", "frequency_metrics"):
                if isinstance(d.get(f), str):
                    try: d[f] = json.loads(d[f])
                    except Exception: pass
            events.append({
                "type": "ingestion",
                "ts": d["timestamp"],
                "risk_score": d["risk_score"],
                "category": d["category"],
                "action_taken": d["action_taken"],
                "escalation_flag": d["escalation_flag"],
                "explanation_snapshot": d.get("explanation_snapshot"),
                "frequency_metrics": d.get("frequency_metrics"),
            })

    # Status changes
    async with db.execute(
        "SELECT * FROM status_history WHERE case_id = ? ORDER BY created_at ASC",
        (case_id,),
    ) as cur:
        for r in await cur.fetchall():
            d = dict(r)
            events.append({
                "type": "status_change",
                "ts": d["created_at"],
                "field": d["field"],
                "old_value": d["old_value"],
                "new_value": d["new_value"],
                "reason": d["reason"],
                "actor_id": d["actor_id"],
                "actor_role": d["actor_role"],
            })

    # Checklist activity (item creation notes)
    async with db.execute(
        """SELECT ci.id, ci.label, ci.status, ci.item_type, ci.created_by, ci.created_at,
                  cn.content, cn.author_id, cn.author_name, cn.created_at as note_at
           FROM checklist_items ci
           LEFT JOIN case_notes cn ON cn.checklist_item_id = ci.id
           WHERE ci.case_id = ?
           ORDER BY ci.created_at ASC, cn.created_at ASC""",
        (case_id,),
    ) as cur:
        for r in await cur.fetchall():
            d = dict(r)
            events.append({
                "type": "checklist_activity",
                "ts": d["note_at"] or d["created_at"],
                "item_label": d["label"],
                "item_type": d["item_type"],
                "item_status": d["status"],
                "note": d["content"],
                "actor_id": d["author_id"] or d["created_by"],
                "actor_name": d["author_name"],
            })

    # Reassignment requests
    async with db.execute(
        "SELECT * FROM reassignment_requests WHERE case_id = ? ORDER BY created_at ASC",
        (case_id,),
    ) as cur:
        for r in await cur.fetchall():
            d = dict(r)
            events.append({
                "type": "reassignment_request",
                "ts": d["created_at"],
                "requested_by": d["requested_by"],
                "requested_to": d["requested_to"],
                "reason": d["reason"],
                "status": d["status"],
                "reviewed_by": d["reviewed_by"],
                "reviewed_at": d["reviewed_at"],
            })

    # Case-level notes (not linked to checklist items)
    async with db.execute(
        """SELECT * FROM case_notes WHERE case_id = ? AND checklist_item_id IS NULL
           ORDER BY created_at ASC""",
        (case_id,),
    ) as cur:
        for r in await cur.fetchall():
            d = dict(r)
            events.append({
                "type": "note",
                "ts": d["created_at"],
                "content": d["content"],
                "actor_id": d["author_id"],
                "actor_name": d["author_name"],
            })

    # Sort everything chronologically
    events.sort(key=lambda e: e.get("ts") or "")
    return events


# ─── Update work status (helper or admin) ─────────────────────────────────────
@router.patch("/{case_id}/work-status")
async def update_work_status(case_id: str, request: Request):
    """
    Youth Helpers update the operational progress of their assigned case.
    Selecting 'to_review' requires a mandatory reason, sets needs_review=1,
    and is fully logged in status_history and audit_log.
    """
    user = get_current_user(request)
    db = await get_db()
    await _assert_case_access(db, case_id, user)

    body = await request.json()
    new_work_status = body.get("work_status", "").strip()
    reason = body.get("reason", "").strip()

    valid = {"not_started", "in_progress", "to_review", "completed"}
    if new_work_status not in valid:
        raise HTTPException(400, f"work_status must be one of {sorted(valid)}")

    # Mandatory reason when submitting for review
    if new_work_status == "to_review" and not reason:
        raise HTTPException(
            422,
            {
                "code": "REASON_REQUIRED",
                "message": "A reason is required when setting work_status to 'to_review'.",
            },
        )

    # Fetch current value for history record
    async with db.execute(
        "SELECT work_status FROM cases WHERE case_id = ?", (case_id,)
    ) as cur:
        row = await cur.fetchone()
    old_work_status = row["work_status"] if row else None

    needs_review = 1 if new_work_status == "to_review" else 0

    await db.execute(
        "UPDATE cases SET work_status = ?, needs_review = ? WHERE case_id = ?",
        (new_work_status, needs_review, case_id),
    )
    await _record_status_change(
        db, case_id, "work_status", old_work_status, new_work_status, user, reason or None
    )
    await _audit(db, user, "UPDATE_WORK_STATUS", case_id, {
        "old": old_work_status, "new": new_work_status, "reason": reason or None
    })
    await db.commit()
    return {
        "case_id": case_id,
        "work_status": new_work_status,
        "needs_review": needs_review,
    }


# ─── Update case status (admin or own-case helper for legacy compat) ──────────
@router.patch("/{case_id}/status")
async def update_case_status(case_id: str, request: Request):
    user = get_current_user(request)
    body = await request.json()
    new_status = body.get("status")
    valid = {"new", "in_progress", "in_review", "outreach", "followup", "completed", "closed"}
    if new_status not in valid:
        raise HTTPException(400, f"status must be one of {valid}")

    db = await get_db()
    await _assert_case_access(db, case_id, user)

    await db.execute(
        "UPDATE cases SET status = ? WHERE case_id = ?", (new_status, case_id)
    )
    await _audit(db, user, "UPDATE_LEGACY_STATUS", case_id, {"new": new_status})
    await db.commit()
    return {"case_id": case_id, "status": new_status}


# ─── Update priority (admin only) ────────────────────────────────────────────
@router.patch("/{case_id}/priority")
async def update_priority(case_id: str, request: Request):
    user = await require_admin(request)
    body = await request.json()
    priority = body.get("priority")
    if priority not in {"low", "medium", "high", "critical"}:
        raise HTTPException(400, "Invalid priority")
    db = await get_db()
    await db.execute(
        "UPDATE cases SET priority = ? WHERE case_id = ?", (priority, case_id)
    )
    await _audit(db, user, "UPDATE_PRIORITY", case_id, {"priority": priority})
    await db.commit()
    return {"case_id": case_id, "priority": priority}


# ─── Assign / Reassign (admin only) ──────────────────────────────────────────
@router.patch("/{case_id}/assign")
async def assign_case(case_id: str, request: Request):
    user = await require_admin(request)
    body = await request.json()
    assigned_to = body.get("assigned_to")  # None to unassign

    db = await get_db()
    async with db.execute(
        "SELECT assigned_to, case_status, work_status FROM cases WHERE case_id = ?", (case_id,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Case not found")

    old_case_status = row["case_status"]
    old_work_status = row["work_status"]
    new_case_status = "assigned" if assigned_to else "unassigned"
    # When first assigned, default work_status to not_started
    new_work_status = "not_started" if (assigned_to and old_case_status != "assigned") else old_work_status

    await db.execute(
        """UPDATE cases
           SET assigned_to = ?, case_status = ?, work_status = ?
           WHERE case_id = ?""",
        (assigned_to, new_case_status, new_work_status, case_id),
    )
    if old_case_status != new_case_status:
        await _record_status_change(db, case_id, "case_status", old_case_status, new_case_status, user)
    if old_work_status != new_work_status:
        await _record_status_change(db, case_id, "work_status", old_work_status, new_work_status, user,
                                    reason="Defaulted to not_started on assignment")
    await _audit(db, user, "ASSIGN_CASE", case_id, {
        "assigned_to": assigned_to,
        "case_status": new_case_status,
        "work_status": new_work_status,
    })
    await db.commit()
    return {
        "case_id": case_id,
        "assigned_to": assigned_to,
        "case_status": new_case_status,
        "work_status": new_work_status,
    }


# ─── Submit reassignment request (helper) ────────────────────────────────────
@router.post("/{case_id}/reassignment-request")
async def request_reassignment(case_id: str, request: Request):
    user = get_current_user(request)
    body = await request.json()
    reason = (body.get("reason") or "").strip()
    requested_to = body.get("requested_to")

    if not reason:
        raise HTTPException(400, "reason is required")

    db = await get_db()
    row = await _assert_case_access(db, case_id, user)

    # Set case_status to 'reassigned' (pending admin review)
    async with db.execute(
        "SELECT case_status FROM cases WHERE case_id = ?", (case_id,)
    ) as cur:
        cs_row = await cur.fetchone()
    old_cs = cs_row["case_status"] if cs_row else "assigned"

    await db.execute(
        "INSERT INTO reassignment_requests (case_id, requested_by, requested_to, reason, status, created_at) VALUES (?,?,?,?,?,?)",
        (case_id, user.user_id, requested_to, reason, "pending", _now_iso()),
    )
    await db.execute(
        "UPDATE cases SET case_status = 'reassigned' WHERE case_id = ?", (case_id,)
    )
    await _record_status_change(db, case_id, "case_status", old_cs, "reassigned", user, reason=reason)
    await _audit(db, user, "REQUEST_REASSIGNMENT", case_id, {"reason": reason, "requested_to": requested_to})
    await db.commit()
    return {"case_id": case_id, "case_status": "reassigned", "request_status": "pending"}


# ─── Approve / Reject reassignment (admin) ───────────────────────────────────
@router.patch("/reassignment/{request_id}")
async def review_reassignment(request_id: int, request: Request):
    user = await require_admin(request)
    body = await request.json()
    decision = body.get("decision")
    if decision not in {"approved", "rejected"}:
        raise HTTPException(400, "decision must be 'approved' or 'rejected'")

    db = await get_db()
    async with db.execute(
        "SELECT * FROM reassignment_requests WHERE id = ?", (request_id,)
    ) as cur:
        rr = await cur.fetchone()
    if not rr:
        raise HTTPException(404, "Request not found")

    await db.execute(
        "UPDATE reassignment_requests SET status=?, reviewed_by=?, reviewed_at=? WHERE id=?",
        (decision, user.user_id, _now_iso(), request_id),
    )

    case_id = rr["case_id"]
    if decision == "approved" and rr["requested_to"]:
        # Re-assign and reset work_status
        async with db.execute("SELECT case_status, work_status FROM cases WHERE case_id=?", (case_id,)) as cur:
            c = await cur.fetchone()
        await db.execute(
            "UPDATE cases SET assigned_to=?, case_status='assigned', work_status='not_started' WHERE case_id=?",
            (rr["requested_to"], case_id),
        )
        await _record_status_change(db, case_id, "case_status", c["case_status"], "assigned", user,
                                    reason=f"Reassignment approved → {rr['requested_to']}")
        await _record_status_change(db, case_id, "work_status", c["work_status"], "not_started", user,
                                    reason="Reset on reassignment")
    elif decision == "rejected":
        # Revert case_status back to assigned
        await db.execute(
            "UPDATE cases SET case_status='assigned' WHERE case_id=? AND case_status='reassigned'",
            (case_id,),
        )

    await _audit(db, user, "REVIEW_REASSIGNMENT", case_id,
                 {"request_id": request_id, "decision": decision})
    await db.commit()
    return {"request_id": request_id, "decision": decision}


# ─── Get all reassignment requests (admin) ────────────────────────────────────
@router.get("/reassignment/all")
async def list_reassignment_requests(request: Request, status: Optional[str] = None):
    user = await require_admin(request)
    db = await get_db()
    query = "SELECT * FROM reassignment_requests WHERE 1=1"
    params: list = []
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC"
    async with db.execute(query, params) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]



def _row_to_dict(row) -> dict:
    d = dict(row)
    for field in ("explanation_signals",):
        if field in d and isinstance(d[field], str):
            try:
                d[field] = json.loads(d[field])
            except Exception:
                pass
    return d


# ─── List cases (summary) ────────────────────────────────────────────────────
@router.get("/summary")
async def list_cases_summary(
    request: Request,
    category: Optional[str] = None,
    status: Optional[str] = None,
    assigned_to: Optional[str] = None,
):
    user = get_current_user(request)
    db = await get_db()
    query = """
        SELECT case_id, user_id, assigned_to, risk_score, category,
               status, priority, needs_review, created_at, last_signal_at
        FROM cases WHERE 1=1
    """
    params = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if status:
        query += " AND status = ?"
        params.append(status)
    if assigned_to:
        query += " AND assigned_to = ?"
        params.append(assigned_to)
    query += " ORDER BY risk_score DESC, created_at DESC"

    async with db.execute(query, params) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


# ─── Assigned cases (helper's own) ──────────────────────────────────────────
@router.get("/assigned")
async def list_assigned_cases(request: Request):
    user = get_current_user(request)
    db = await get_db()
    async with db.execute(
        """
        SELECT case_id, user_id, assigned_to, risk_score, category,
               explanation_signals, status, priority, needs_review,
               created_at, last_signal_at
        FROM cases WHERE assigned_to = ?
        ORDER BY risk_score DESC, created_at DESC
        """,
        (user.user_id,),
    ) as cur:
        rows = await cur.fetchall()
    return [_row_to_dict(r) for r in rows]


# ─── Needs Review (admin tab) ─────────────────────────────────────────────────
@router.get("/needs-review")
async def list_needs_review(request: Request):
    user = get_current_user(request)
    if not user.is_admin:
        raise HTTPException(403, "Admin only")
    db = await get_db()
    async with db.execute(
        "SELECT * FROM cases WHERE needs_review = 1 ORDER BY risk_score DESC",
    ) as cur:
        rows = await cur.fetchall()
    return [_row_to_dict(r) for r in rows]


# ─── Get single case (full detail) ───────────────────────────────────────────
@router.get("/{case_id}")
async def get_case(case_id: str, request: Request):
    user = get_current_user(request)
    db = await get_db()

    async with db.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Case not found")

    case = _row_to_dict(row)

    # Helpers can only see full detail for their assigned cases
    if user.is_helper and case.get("assigned_to") != user.user_id:
        # Return summary only
        return {
            k: v
            for k, v in case.items()
            if k
            in (
                "case_id",
                "user_id",
                "assigned_to",
                "risk_score",
                "category",
                "status",
                "priority",
                "needs_review",
                "created_at",
                "last_signal_at",
            )
        }

    # Attach checklist
    async with db.execute(
        "SELECT * FROM checklist_items WHERE case_id = ? ORDER BY id",
        (case_id,),
    ) as cur:
        checklist = [dict(r) for r in await cur.fetchall()]

    # Attach pending reassignment requests
    async with db.execute(
        "SELECT * FROM reassignment_requests WHERE case_id = ? AND status='pending'",
        (case_id,),
    ) as cur:
        reassigns = [dict(r) for r in await cur.fetchall()]

    case["checklist"] = checklist
    case["pending_reassignments"] = reassigns
    return case


# ─── Update case status / priority (admin override or own-case helper) ───────
@router.patch("/{case_id}/status")
async def update_case_status(case_id: str, request: Request):
    user = get_current_user(request)
    body = await request.json()
    new_status = body.get("status")
    valid = {"new", "in_progress", "in_review", "outreach", "followup", "completed", "closed"}
    if new_status not in valid:
        raise HTTPException(400, f"status must be one of {valid}")

    db = await get_db()
    async with db.execute("SELECT assigned_to FROM cases WHERE case_id = ?", (case_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Case not found")

    if user.is_helper and row["assigned_to"] != user.user_id:
        raise HTTPException(403, "Can only update status on your assigned cases")

    await db.execute(
        "UPDATE cases SET status = ? WHERE case_id = ?", (new_status, case_id)
    )
    await db.commit()
    return {"case_id": case_id, "status": new_status}


# ─── Update priority (admin only) ────────────────────────────────────────────
@router.patch("/{case_id}/priority")
async def update_priority(case_id: str, request: Request):
    user = get_current_user(request)
    if not user.is_admin:
        raise HTTPException(403, "Admin only")
    body = await request.json()
    priority = body.get("priority")
    if priority not in {"low", "medium", "high", "critical"}:
        raise HTTPException(400, "Invalid priority")
    db = await get_db()
    await db.execute(
        "UPDATE cases SET priority = ? WHERE case_id = ?", (priority, case_id)
    )
    await db.commit()
    return {"case_id": case_id, "priority": priority}


# ─── Assign / Reassign (admin only) ──────────────────────────────────────────
@router.patch("/{case_id}/assign")
async def assign_case(case_id: str, request: Request):
    user = await require_admin(request)
    body = await request.json()
    assigned_to = body.get("assigned_to")
    db = await get_db()
    await db.execute(
        "UPDATE cases SET assigned_to = ? WHERE case_id = ?", (assigned_to, case_id)
    )
    await db.commit()
    return {"case_id": case_id, "assigned_to": assigned_to}


# ─── Submit reassignment request (helper) ────────────────────────────────────
@router.post("/{case_id}/reassignment-request")
async def request_reassignment(case_id: str, request: Request):
    user = get_current_user(request)
    body = await request.json()
    reason = body.get("reason", "")
    requested_to = body.get("requested_to")

    db = await get_db()
    async with db.execute("SELECT assigned_to FROM cases WHERE case_id = ?", (case_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Case not found")
    if row["assigned_to"] != user.user_id and not user.is_admin:
        raise HTTPException(403, "Not your case")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    await db.execute(
        """INSERT INTO reassignment_requests
           (case_id, requested_by, requested_to, reason, status, created_at)
           VALUES (?,?,?,?,?,?)""",
        (case_id, user.user_id, requested_to, reason, "pending", now),
    )
    await db.commit()
    return {"case_id": case_id, "status": "pending"}


# ─── Approve / Reject reassignment (admin) ────────────────────────────────────
@router.patch("/reassignment/{request_id}")
async def review_reassignment(request_id: int, request: Request):
    user = await require_admin(request)
    body = await request.json()
    decision = body.get("decision")  # approved | rejected
    if decision not in {"approved", "rejected"}:
        raise HTTPException(400, "decision must be 'approved' or 'rejected'")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    db = await get_db()

    async with db.execute(
        "SELECT * FROM reassignment_requests WHERE id = ?", (request_id,)
    ) as cur:
        rr = await cur.fetchone()
    if not rr:
        raise HTTPException(404, "Request not found")

    await db.execute(
        "UPDATE reassignment_requests SET status=?, reviewed_by=?, reviewed_at=? WHERE id=?",
        (decision, user.user_id, now, request_id),
    )
    if decision == "approved" and rr["requested_to"]:
        await db.execute(
            "UPDATE cases SET assigned_to = ? WHERE case_id = ?",
            (rr["requested_to"], rr["case_id"]),
        )
    await db.commit()
    return {"request_id": request_id, "decision": decision}
