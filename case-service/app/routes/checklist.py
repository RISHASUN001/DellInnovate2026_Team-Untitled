import json
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from ..database import get_db
from ..auth import get_current_user

router = APIRouter(prefix="/cases/{case_id}/checklist", tags=["checklist"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def _assert_case_access(db, case_id: str, user):
    async with db.execute("SELECT assigned_to FROM cases WHERE case_id = ?", (case_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Case not found")
    if user.is_helper and row["assigned_to"] != user.user_id:
        raise HTTPException(403, "Not your assigned case")
    return row


# ─── List checklist items for a case ─────────────────────────────────────────
@router.get("")
async def list_checklist(case_id: str, request: Request):
    user = get_current_user(request)
    db = await get_db()
    await _assert_case_access(db, case_id, user)

    async with db.execute(
        "SELECT * FROM checklist_items WHERE case_id = ? ORDER BY COALESCE(parent_id, id), id",
        (case_id,),
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]
    return rows


# ─── Add checklist item (human or agent) ─────────────────────────────────────
@router.post("")
async def add_checklist_item(case_id: str, request: Request):
    user = get_current_user(request)
    db = await get_db()
    await _assert_case_access(db, case_id, user)

    body = await request.json()
    label = body.get("label", "").strip()
    if not label:
        raise HTTPException(400, "label required")
    parent_id = body.get("parent_id")
    mandatory = 1 if body.get("mandatory", False) else 0
    created_by = body.get("created_by", "human")  # 'agent' | 'human'

    await db.execute(
        """INSERT INTO checklist_items (case_id, parent_id, label, status, mandatory, created_by, created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (case_id, parent_id, label, "Not Started", mandatory, created_by, _now_iso()),
    )
    await db.commit()
    # Return the new item
    async with db.execute(
        "SELECT * FROM checklist_items WHERE case_id = ? ORDER BY id DESC LIMIT 1", (case_id,)
    ) as cur:
        row = await cur.fetchone()
    return dict(row)


# ─── Update checklist item status + required comment ─────────────────────────
@router.patch("/{item_id}/status")
async def update_checklist_item_status(case_id: str, item_id: int, request: Request):
    user = get_current_user(request)
    db = await get_db()
    await _assert_case_access(db, case_id, user)

    body = await request.json()
    new_status = body.get("status")
    comment = body.get("comment", "").strip()

    valid_statuses = {"Not Started", "In Progress", "Completed", "Needs Review"}
    if new_status not in valid_statuses:
        raise HTTPException(400, f"status must be one of {valid_statuses}")
    if not comment:
        raise HTTPException(400, "A comment is required when changing checklist item status")

    async with db.execute(
        "SELECT id FROM checklist_items WHERE id = ? AND case_id = ?", (item_id, case_id)
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Checklist item not found")

    # Update item status
    await db.execute(
        "UPDATE checklist_items SET status = ? WHERE id = ?",
        (new_status, item_id),
    )

    # Persist the required comment
    await db.execute(
        """INSERT INTO case_notes (case_id, checklist_item_id, author_id, content, created_at)
           VALUES (?,?,?,?,?)""",
        (case_id, item_id, user.user_id, comment, _now_iso()),
    )

    # If any item is Needs Review → flag the case
    if new_status == "Needs Review":
        await db.execute(
            "UPDATE cases SET needs_review = 1 WHERE case_id = ?", (case_id,)
        )
    else:
        # Check if any other items are still Needs Review
        async with db.execute(
            "SELECT COUNT(*) FROM checklist_items WHERE case_id = ? AND status = 'Needs Review'",
            (case_id,),
        ) as cur:
            nr_count = (await cur.fetchone())[0]
        if nr_count == 0:
            await db.execute(
                "UPDATE cases SET needs_review = 0 WHERE case_id = ?", (case_id,)
            )

    await db.commit()
    return {"item_id": item_id, "status": new_status, "comment_saved": True}


# ─── Get notes for a case (optionally filtered by checklist item) ─────────────
@router.get("/{item_id}/notes")
async def get_item_notes(case_id: str, item_id: int, request: Request):
    user = get_current_user(request)
    db = await get_db()
    await _assert_case_access(db, case_id, user)
    async with db.execute(
        "SELECT * FROM case_notes WHERE case_id = ? AND checklist_item_id = ? ORDER BY created_at",
        (case_id, item_id),
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]
