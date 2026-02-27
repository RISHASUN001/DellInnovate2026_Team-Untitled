import json
from datetime import datetime, timezone
from .database import get_db


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def audit_log(
    tool_name: str,
    actor_id: str,
    actor_role: str,
    payload: dict,
    result: dict,
) -> None:
    db = await get_db()
    await db.execute(
        "INSERT INTO audit_log (tool_name, actor_id, actor_role, payload, result, created_at) VALUES (?,?,?,?,?,?)",
        (
            tool_name,
            actor_id,
            actor_role,
            json.dumps(payload),
            json.dumps(result),
            _now_iso(),
        ),
    )
    await db.commit()
