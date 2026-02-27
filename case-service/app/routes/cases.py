import json
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from ..database import get_db
from ..auth import get_current_user, require_admin, AuthUser

router = APIRouter(prefix="/cases", tags=["cases"])


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
