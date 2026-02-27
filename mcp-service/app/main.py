"""
MCP Service — Tool Gateway
The LLM (chatbot-service) proposes actions; the frontend calls this service
to execute them after user approval. All executions are audit-logged.

Route pattern: POST /tools/{tool_name}
Each route validates role + assignment, executes, audits.
"""
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger

from .config import settings
from .database import get_db, close_db
from .auth import get_current_user, require_admin
from .tools import (
    tool_get_case,
    tool_list_cases_summary,
    tool_list_assigned_cases,
    tool_get_case_history,
    tool_search_protocol,
    tool_get_similar_cases,
    tool_update_checklist_item_status,
    tool_add_subtask,
    tool_add_case_note,
    tool_schedule_followup,
    tool_update_case_status,
    tool_update_priority,
    tool_request_reassignment,
    tool_assign_case,
)
from .audit import audit_log


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("mcp-service starting up...")
    await get_db()  # connect + ensure audit_log table
    yield
    await close_db()
    logger.info("mcp-service shut down.")


app = FastAPI(
    title="SCS MCP Service",
    description="Tool gateway — executes approved LLM-proposed actions with audit logging",
    version="1.0.0",
    lifespan=lifespan,
)

origins = [o.strip() for o in settings.allowed_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── READ TOOLS ──────────────────────────────────────────────────────────────

@app.get("/tools/get_case/{case_id}")
async def get_case(case_id: str, request: Request):
    user = get_current_user(request)
    return await tool_get_case(case_id, user)


@app.get("/tools/list_cases_summary")
async def list_cases_summary(
    request: Request,
    category: Optional[str] = None,
    status: Optional[str] = None,
):
    user = get_current_user(request)
    return await tool_list_cases_summary(user, category=category, status=status)


@app.get("/tools/list_assigned_cases")
async def list_assigned_cases(request: Request):
    user = get_current_user(request)
    return await tool_list_assigned_cases(user)


@app.get("/tools/get_case_history/{case_id}")
async def get_case_history(case_id: str, request: Request):
    user = get_current_user(request)
    return await tool_get_case_history(case_id, user)


class ProtocolSearchRequest(BaseModel):
    query: str


@app.post("/tools/search_protocol")
async def search_protocol(body: ProtocolSearchRequest, request: Request):
    user = get_current_user(request)
    return await tool_search_protocol(body.query, user)


@app.get("/tools/get_similar_cases/{case_id}")
async def get_similar_cases(case_id: str, request: Request, top_k: int = 5):
    user = get_current_user(request)
    return await tool_get_similar_cases(case_id, user, top_k=top_k)


# ─── WRITE TOOLS ─────────────────────────────────────────────────────────────

class ChecklistStatusRequest(BaseModel):
    case_id: str
    item_id: int
    new_status: str
    comment: str


@app.post("/tools/update_checklist_item_status")
async def update_checklist_item_status(body: ChecklistStatusRequest, request: Request):
    user = get_current_user(request)
    return await tool_update_checklist_item_status(
        body.case_id, body.item_id, body.new_status, body.comment, user
    )


class AddSubtaskRequest(BaseModel):
    case_id: str
    parent_id: int
    label: str
    mandatory: bool = False


@app.post("/tools/add_subtask")
async def add_subtask(body: AddSubtaskRequest, request: Request):
    user = get_current_user(request)
    return await tool_add_subtask(body.case_id, body.parent_id, body.label, body.mandatory, user)


class CaseNoteRequest(BaseModel):
    case_id: str
    content: str


@app.post("/tools/add_case_note")
async def add_case_note(body: CaseNoteRequest, request: Request):
    user = get_current_user(request)
    return await tool_add_case_note(body.case_id, body.content, user)


class FollowupRequest(BaseModel):
    case_id: str
    scheduled_at: str
    note: Optional[str] = ""


@app.post("/tools/schedule_followup")
async def schedule_followup(body: FollowupRequest, request: Request):
    user = get_current_user(request)
    return await tool_schedule_followup(body.case_id, body.scheduled_at, body.note or "", user)


class CaseStatusRequest(BaseModel):
    case_id: str
    status: str


@app.post("/tools/update_case_status")
async def update_case_status(body: CaseStatusRequest, request: Request):
    user = get_current_user(request)
    return await tool_update_case_status(body.case_id, body.status, user)


class PriorityRequest(BaseModel):
    case_id: str
    priority: str


@app.post("/tools/update_priority")
async def update_priority(body: PriorityRequest, request: Request):
    user = get_current_user(request)
    return await tool_update_priority(body.case_id, body.priority, user)


class ReassignmentRequest(BaseModel):
    case_id: str
    reason: str
    requested_to: Optional[str] = None


@app.post("/tools/request_reassignment")
async def request_reassignment(body: ReassignmentRequest, request: Request):
    user = get_current_user(request)
    return await tool_request_reassignment(body.case_id, body.reason, user, body.requested_to)


class AssignCaseRequest(BaseModel):
    case_id: str
    assigned_to: str


@app.post("/tools/assign_case")
async def assign_case(body: AssignCaseRequest, request: Request):
    user = get_current_user(request)
    return await tool_assign_case(body.case_id, body.assigned_to, user)


# ─── Audit log viewer (admin only) ───────────────────────────────────────────

@app.get("/audit-log")
async def get_audit_log(request: Request, limit: int = 50):
    user = require_admin(request)
    import json as _json
    db = await get_db()
    async with db.execute(
        "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]
    for r in rows:
        for f in ("payload", "result"):
            if isinstance(r.get(f), str):
                try:
                    r[f] = _json.loads(r[f])
                except Exception:
                    pass
    return rows


@app.get("/tools")
async def list_tools():
    return {
        "read_tools": [
            "get_case", "list_cases_summary", "list_assigned_cases",
            "get_case_history", "search_protocol", "get_similar_cases",
        ],
        "write_tools": [
            "update_checklist_item_status", "add_subtask", "add_case_note",
            "schedule_followup", "update_case_status", "update_priority",
            "request_reassignment", "assign_case",
        ],
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "mcp-service"}
