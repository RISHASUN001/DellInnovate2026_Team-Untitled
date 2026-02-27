import json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from ..database import get_db
from ..auth import get_current_user

router = APIRouter(prefix="/cases/{case_id}/history", tags=["history"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─── Full ingestion history (timeline) ───────────────────────────────────────
@router.get("")
async def get_case_history(case_id: str, request: Request):
    user = get_current_user(request)
    db = await get_db()

    async with db.execute("SELECT assigned_to FROM cases WHERE case_id = ?", (case_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Case not found")

    # Admins see all; helpers see history only for their assigned cases
    if user.is_helper and row["assigned_to"] != user.user_id:
        raise HTTPException(403, "Not your assigned case")

    async with db.execute(
        """SELECT id, case_id, risk_score, category, explanation_snapshot,
                  frequency_metrics, action_taken, escalation_flag, timestamp
           FROM case_history WHERE case_id = ? ORDER BY timestamp ASC""",
        (case_id,),
    ) as cur:
        rows = await cur.fetchall()

    result = []
    for r in rows:
        d = dict(r)
        for field in ("explanation_snapshot", "frequency_metrics"):
            if isinstance(d.get(field), str):
                try:
                    d[field] = json.loads(d[field])
                except Exception:
                    pass
        result.append(d)
    return result
