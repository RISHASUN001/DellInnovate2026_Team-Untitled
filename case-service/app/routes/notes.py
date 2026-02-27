from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from ..database import get_db
from ..auth import get_current_user

router = APIRouter(prefix="/cases/{case_id}", tags=["notes", "followups"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def _assert_access(db, case_id: str, user):
    async with db.execute("SELECT assigned_to FROM cases WHERE case_id = ?", (case_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Case not found")
    if user.is_helper and row["assigned_to"] != user.user_id:
        raise HTTPException(403, "Not your assigned case")


# ─── Notes ────────────────────────────────────────────────────────────────────
@router.get("/notes")
async def list_notes(case_id: str, request: Request):
    user = get_current_user(request)
    db = await get_db()
    await _assert_access(db, case_id, user)
    async with db.execute(
        "SELECT * FROM case_notes WHERE case_id = ? ORDER BY created_at", (case_id,)
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


@router.post("/notes")
async def add_note(case_id: str, request: Request):
    user = get_current_user(request)
    body = await request.json()
    content = body.get("content", "").strip()
    if not content:
        raise HTTPException(400, "content required")
    db = await get_db()
    await _assert_access(db, case_id, user)
    await db.execute(
        "INSERT INTO case_notes (case_id, checklist_item_id, author_id, content, created_at) VALUES (?,?,?,?,?)",
        (case_id, None, user.user_id, content, _now_iso()),
    )
    await db.commit()
    return {"case_id": case_id, "saved": True}


# ─── Follow-ups ───────────────────────────────────────────────────────────────
@router.get("/followups")
async def list_followups(case_id: str, request: Request):
    user = get_current_user(request)
    db = await get_db()
    await _assert_access(db, case_id, user)
    async with db.execute(
        "SELECT * FROM followups WHERE case_id = ? ORDER BY scheduled_at", (case_id,)
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]


@router.post("/followups")
async def schedule_followup(case_id: str, request: Request):
    user = get_current_user(request)
    db = await get_db()
    await _assert_access(db, case_id, user)

    body = await request.json()
    scheduled_at = body.get("scheduled_at")
    note = body.get("note", "")
    if not scheduled_at:
        raise HTTPException(400, "scheduled_at required (ISO8601)")

    await db.execute(
        "INSERT INTO followups (case_id, scheduled_at, note, created_by, completed, created_at) VALUES (?,?,?,?,?,?)",
        (case_id, scheduled_at, note, user.user_id, 0, _now_iso()),
    )
    await db.commit()
    return {"case_id": case_id, "scheduled_at": scheduled_at}
