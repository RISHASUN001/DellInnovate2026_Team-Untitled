"""
Audit logging for all MCP tool calls (read and write).

Every log entry captures:
  request_id        — correlates a chain of calls
  case_id           — the case being acted on (empty for list operations)
  approved_plan_hash — populated only for write tools executed via /execute-approved-plan
  tool_name         — the MCP tool invoked
  actor_id / role   — who triggered the call
  payload           — arguments (write payloads truncated to 500 chars for PII safety)
  result            — tool outcome
  created_at        — UTC ISO8601
"""
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
    *,
    request_id: str = "",
    case_id: str = "",
    approved_plan_hash: str = "",
) -> None:
    db = await get_db()
    audit_col = db['mcp_audit_log']
    
    # Truncate large payloads (e.g. outreach message bodies)
    payload_str = json.dumps(payload)
    if len(payload_str) > 500:
        payload_str = payload_str[:497] + "..."
    
    await audit_col.insert_one({
        "tool_name": tool_name,
        "actor_id": actor_id,
        "actor_role": actor_role,
        "payload": payload_str,
        "result": json.dumps(result),
        "request_id": request_id,
        "case_id": case_id,
        "approved_plan_hash": approved_plan_hash,
        "created_at": _now_iso(),
    })

