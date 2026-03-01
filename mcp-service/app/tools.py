"""
MCP Tool Definitions.

READ TOOLS  (no DB writes, no approval needed):
  get_case, list_cases_summary, list_assigned_cases,
  get_case_history, search_protocol, get_similar_cases

WRITE TOOLS (approval-gated — called only via /execute-approved-plan):
  add_checklist_item, update_checklist_item_status, add_subtask,
  add_case_note, schedule_followup, update_case_status,
  update_priority, request_reassignment, assign_case,
  flag_for_escalation

Every tool:
  - validates role + assignment
  - calls the SQLite DB directly (LLM never accesses DB)
  - logs via audit_log with request_id, case_id, approved_plan_hash
"""
import json
import httpx
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from fastapi import HTTPException

from .database import get_db
from .audit import audit_log
from .auth import AuthUser
from .config import settings


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hours_from_now_iso(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


async def _row_to_dict_json(row) -> dict:
    d = dict(row)
    for field in ("explanation_signals", "explanation_snapshot", "frequency_metrics"):
        if field in d and isinstance(d[field], str):
            try:
                d[field] = json.loads(d[field])
            except Exception:
                pass
    return d


async def _assert_case_write_access(db, case_id: str, user: AuthUser) -> dict:
    """Returns case row; raises 403/404 if not allowed."""
    async with db.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, f"Case {case_id} not found")
    case = dict(row)
    if user.is_helper and case.get("assigned_to") != user.user_id:
        raise HTTPException(403, "You can only modify your assigned cases")
    return case


# ─── READ TOOLS ──────────────────────────────────────────────────────────────

async def tool_get_case(case_id: str, user: AuthUser) -> dict:
    db = await get_db()
    async with db.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Case not found")
    case = await _row_to_dict_json(row)

    if user.is_helper and case.get("assigned_to") != user.user_id:
        allowed = {"case_id", "user_id", "assigned_to", "risk_score", "category",
                   "status", "priority", "created_at", "last_signal_at"}
        case = {k: v for k, v in case.items() if k in allowed}

    await audit_log("get_case", user.user_id, user.role,
                    {"case_id": case_id}, {"found": True},
                    case_id=case_id)
    return case


async def tool_list_cases_summary(
    user: AuthUser,
    category: Optional[str] = None,
    status: Optional[str] = None,
) -> list[dict]:
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
    query += " ORDER BY risk_score DESC, created_at DESC"

    async with db.execute(query, params) as cur:
        rows = [dict(r) for r in await cur.fetchall()]

    await audit_log(
        "list_cases_summary", user.user_id, user.role,
        {"category": category, "status": status}, {"count": len(rows)}
    )
    return rows


async def tool_list_assigned_cases(user: AuthUser) -> list[dict]:
    db = await get_db()
    async with db.execute(
        """SELECT case_id, user_id, assigned_to, risk_score, category,
                  explanation_signals, status, priority, needs_review,
                  created_at, last_signal_at
           FROM cases WHERE assigned_to = ? ORDER BY risk_score DESC""",
        (user.user_id,),
    ) as cur:
        rows = await cur.fetchall()
    result = [await _row_to_dict_json(r) for r in rows]
    await audit_log("list_assigned_cases", user.user_id, user.role, {}, {"count": len(result)})
    return result


async def tool_get_case_history(case_id: str, user: AuthUser) -> list[dict]:
    db = await get_db()
    async with db.execute("SELECT assigned_to FROM cases WHERE case_id = ?", (case_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Case not found")
    if user.is_helper and row["assigned_to"] != user.user_id:
        raise HTTPException(403, "Not your assigned case")

    async with db.execute(
        "SELECT * FROM case_history WHERE case_id = ? ORDER BY timestamp ASC", (case_id,)
    ) as cur:
        rows = await cur.fetchall()
    result = [await _row_to_dict_json(r) for r in rows]
    await audit_log("get_case_history", user.user_id, user.role,
                    {"case_id": case_id}, {"rows": len(result)},
                    case_id=case_id)
    return result


async def tool_search_protocol(query: str, user: AuthUser) -> dict:
    """Delegates to chatbot-service RAG search."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.chatbot_service_url}/chat",
                json={"messages": [{"role": "user", "content": f"Protocol search: {query}"}]},
                headers={"X-User-Id": user.user_id, "X-User-Role": user.role},
            )
        result = resp.json()
    except Exception as e:
        result = {"response_text": f"Protocol search unavailable: {e}", "proposed_actions": []}

    await audit_log("search_protocol", user.user_id, user.role, {"query": query}, {"found": True})
    return result


async def tool_get_similar_cases(case_id: str, user: AuthUser, top_k: int = 5) -> dict:
    """Delegates to chatbot-service similarity endpoint."""
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


# ─── WRITE TOOLS ─────────────────────────────────────────────────────────────

async def tool_add_checklist_item(
    case_id: str,
    label: str,
    mandatory: bool,
    sub_items: list[str],
    user: AuthUser,
    *,
    request_id: str = "",
    approved_plan_hash: str = "",
) -> dict:
    """Add a top-level checklist item, optionally with child sub-items."""
    db = await get_db()
    await _assert_case_write_access(db, case_id, user)

    await db.execute(
        "INSERT INTO checklist_items (case_id, parent_id, label, status, mandatory, created_by, created_at) VALUES (?,?,?,?,?,?,?)",
        (case_id, None, label, "Not Started", 1 if mandatory else 0, "agent", _now_iso()),
    )
    await db.commit()
    async with db.execute(
        "SELECT id FROM checklist_items WHERE case_id = ? AND parent_id IS NULL ORDER BY id DESC LIMIT 1",
        (case_id,),
    ) as cur:
        parent_id = (await cur.fetchone())["id"]

    sub_ids = []
    for sub_label in sub_items:
        await db.execute(
            "INSERT INTO checklist_items (case_id, parent_id, label, status, mandatory, created_by, created_at) VALUES (?,?,?,?,?,?,?)",
            (case_id, parent_id, sub_label, "Not Started", 0, "agent", _now_iso()),
        )
        await db.commit()
        async with db.execute(
            "SELECT id FROM checklist_items WHERE case_id = ? AND parent_id = ? ORDER BY id DESC LIMIT 1",
            (case_id, parent_id),
        ) as cur:
            sub_ids.append((await cur.fetchone())["id"])

    result = {"item_id": parent_id, "sub_item_ids": sub_ids, "label": label}
    await audit_log(
        "add_checklist_item", user.user_id, user.role,
        {"case_id": case_id, "label": label, "sub_items": sub_items},
        result,
        request_id=request_id, case_id=case_id, approved_plan_hash=approved_plan_hash,
    )
    return result


async def tool_update_checklist_item_status(
    case_id: str,
    item_id: int,
    new_status: str,
    comment: str,
    user: AuthUser,
    *,
    request_id: str = "",
    approved_plan_hash: str = "",
) -> dict:
    valid = {"Not Started", "In Progress", "Completed", "Needs Review"}
    if new_status not in valid:
        raise HTTPException(400, f"status must be one of {valid}")
    if not comment:
        raise HTTPException(400, "comment required for status change")

    db = await get_db()
    await _assert_case_write_access(db, case_id, user)

    async with db.execute(
        "SELECT id FROM checklist_items WHERE id = ? AND case_id = ?", (item_id, case_id)
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Checklist item not found")

    await db.execute("UPDATE checklist_items SET status = ? WHERE id = ?", (new_status, item_id))
    await db.execute(
        "INSERT INTO case_notes (case_id, checklist_item_id, author_id, content, created_at) VALUES (?,?,?,?,?)",
        (case_id, item_id, user.user_id, comment, _now_iso()),
    )

    if new_status == "Needs Review":
        await db.execute("UPDATE cases SET needs_review = 1 WHERE case_id = ?", (case_id,))
    else:
        async with db.execute(
            "SELECT COUNT(*) FROM checklist_items WHERE case_id = ? AND status = 'Needs Review'", (case_id,)
        ) as cur:
            nr = (await cur.fetchone())[0]
        if nr == 0:
            await db.execute("UPDATE cases SET needs_review = 0 WHERE case_id = ?", (case_id,))

    await db.commit()
    result = {"item_id": item_id, "status": new_status, "comment_saved": True}
    await audit_log(
        "update_checklist_item_status", user.user_id, user.role,
        {"case_id": case_id, "item_id": item_id, "new_status": new_status, "comment": comment[:80]},
        result,
        request_id=request_id, case_id=case_id, approved_plan_hash=approved_plan_hash,
    )
    return result


async def tool_add_subtask(
    case_id: str,
    parent_id: int,
    label: str,
    mandatory: bool,
    user: AuthUser,
    *,
    request_id: str = "",
    approved_plan_hash: str = "",
) -> dict:
    db = await get_db()
    await _assert_case_write_access(db, case_id, user)

    await db.execute(
        "INSERT INTO checklist_items (case_id, parent_id, label, status, mandatory, created_by, created_at) VALUES (?,?,?,?,?,?,?)",
        (case_id, parent_id, label, "Not Started", 1 if mandatory else 0, "agent", _now_iso()),
    )
    await db.commit()
    async with db.execute(
        "SELECT id FROM checklist_items WHERE case_id = ? ORDER BY id DESC LIMIT 1", (case_id,)
    ) as cur:
        new_id = (await cur.fetchone())["id"]

    result = {"item_id": new_id, "parent_id": parent_id, "label": label}
    await audit_log(
        "add_subtask", user.user_id, user.role,
        {"case_id": case_id, "parent_id": parent_id, "label": label},
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
    db = await get_db()
    await _assert_case_write_access(db, case_id, user)

    tagged_content = f"[{note_type.upper()}] {content}" if note_type != "general" else content
    await db.execute(
        "INSERT INTO case_notes (case_id, checklist_item_id, author_id, content, created_at) VALUES (?,?,?,?,?)",
        (case_id, None, user.user_id, tagged_content, _now_iso()),
    )
    await db.commit()
    result = {"case_id": case_id, "note_type": note_type, "saved": True}
    await audit_log(
        "add_case_note", user.user_id, user.role,
        {"case_id": case_id, "note_type": note_type, "content_len": len(content)},
        result,
        request_id=request_id, case_id=case_id, approved_plan_hash=approved_plan_hash,
    )
    return result


async def tool_schedule_followup(
    case_id: str,
    user: AuthUser,
    note: str = "",
    scheduled_at: Optional[str] = None,
    due_in_hours: Optional[int] = None,
    *,
    request_id: str = "",
    approved_plan_hash: str = "",
) -> dict:
    """Accepts either a scheduled_at ISO timestamp or due_in_hours (relative)."""
    db = await get_db()
    await _assert_case_write_access(db, case_id, user)

    if not scheduled_at:
        hours = due_in_hours or 24
        scheduled_at = _hours_from_now_iso(hours)

    await db.execute(
        "INSERT INTO followups (case_id, scheduled_at, note, created_by, completed, created_at) VALUES (?,?,?,?,?,?)",
        (case_id, scheduled_at, note, user.user_id, 0, _now_iso()),
    )
    await db.commit()
    result = {"case_id": case_id, "scheduled_at": scheduled_at}
    await audit_log(
        "schedule_followup", user.user_id, user.role,
        {"case_id": case_id, "scheduled_at": scheduled_at},
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
    valid = {"new", "in_progress", "in_review", "outreach", "followup", "completed", "closed"}
    if status not in valid:
        raise HTTPException(400, f"Invalid status: {status}")

    db = await get_db()
    await _assert_case_write_access(db, case_id, user)

    await db.execute("UPDATE cases SET status = ? WHERE case_id = ?", (status, case_id))
    await db.commit()
    result = {"case_id": case_id, "status": status}
    await audit_log(
        "update_case_status", user.user_id, user.role,
        {"case_id": case_id, "status": status},
        result,
        request_id=request_id, case_id=case_id, approved_plan_hash=approved_plan_hash,
    )
    return result


async def tool_update_priority(
    case_id: str,
    priority: str,
    user: AuthUser,
    *,
    request_id: str = "",
    approved_plan_hash: str = "",
) -> dict:
    if priority not in {"low", "medium", "high", "critical"}:
        raise HTTPException(400, "Invalid priority")
    if not user.is_admin:
        raise HTTPException(403, "Admin only")

    db = await get_db()
    await db.execute("UPDATE cases SET priority = ? WHERE case_id = ?", (priority, case_id))
    await db.commit()
    result = {"case_id": case_id, "priority": priority}
    await audit_log(
        "update_priority", user.user_id, user.role,
        {"case_id": case_id, "priority": priority},
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
    db = await get_db()
    async with db.execute("SELECT assigned_to FROM cases WHERE case_id = ?", (case_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Case not found")
    if user.is_helper and row["assigned_to"] != user.user_id:
        raise HTTPException(403, "Not your case")

    await db.execute(
        "INSERT INTO reassignment_requests (case_id, requested_by, requested_to, reason, status, created_at) VALUES (?,?,?,?,?,?)",
        (case_id, user.user_id, requested_to, reason, "pending", _now_iso()),
    )
    await db.commit()
    result = {"case_id": case_id, "status": "pending"}
    await audit_log(
        "request_reassignment", user.user_id, user.role,
        {"case_id": case_id, "reason": reason[:100], "requested_to": requested_to},
        result,
        request_id=request_id, case_id=case_id, approved_plan_hash=approved_plan_hash,
    )
    return result


async def tool_assign_case(
    case_id: str,
    assigned_to: str,
    user: AuthUser,
    *,
    request_id: str = "",
    approved_plan_hash: str = "",
) -> dict:
    if not user.is_admin:
        raise HTTPException(403, "Admin only")

    db = await get_db()
    async with db.execute("SELECT case_id FROM cases WHERE case_id = ?", (case_id,)) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Case not found")

    await db.execute("UPDATE cases SET assigned_to = ? WHERE case_id = ?", (assigned_to, case_id))
    await db.commit()
    result = {"case_id": case_id, "assigned_to": assigned_to}
    await audit_log(
        "assign_case", user.user_id, user.role,
        {"case_id": case_id, "assigned_to": assigned_to},
        result,
        request_id=request_id, case_id=case_id, approved_plan_hash=approved_plan_hash,
    )
    return result


async def tool_flag_for_escalation(
    case_id: str,
    reason: str,
    escalation_level: str,
    user: AuthUser,
    *,
    request_id: str = "",
    approved_plan_hash: str = "",
) -> dict:
    """
    Flags a case for escalation:
      - Updates case status to 'in_review' (or 'escalated' for mandatory_reporting)
      - Adds an escalation case note
      - Marks needs_review = 1
    """
    valid_levels = {"internal", "external", "mandatory_reporting"}
    if escalation_level not in valid_levels:
        raise HTTPException(400, f"escalation_level must be one of {valid_levels}")

    db = await get_db()
    await _assert_case_write_access(db, case_id, user)

    new_status = "in_review" if escalation_level == "internal" else "in_review"
    await db.execute(
        "UPDATE cases SET status = ?, needs_review = 1 WHERE case_id = ?",
        (new_status, case_id),
    )
    note_content = (
        f"[ESCALATION — {escalation_level.upper()}] {reason}"
    )
    await db.execute(
        "INSERT INTO case_notes (case_id, checklist_item_id, author_id, content, created_at) VALUES (?,?,?,?,?)",
        (case_id, None, user.user_id, note_content, _now_iso()),
    )
    await db.commit()
    result = {
        "case_id": case_id,
        "escalation_level": escalation_level,
        "status": new_status,
        "note_saved": True,
    }
    await audit_log(
        "flag_for_escalation", user.user_id, user.role,
        {"case_id": case_id, "reason": reason[:120], "escalation_level": escalation_level},
        result,
        request_id=request_id, case_id=case_id, approved_plan_hash=approved_plan_hash,
    )
    return result
