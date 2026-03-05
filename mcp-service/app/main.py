"""
MCP Service — Tool Gateway (v2.0 — two-phase approval-gated)

READ surface (no pre-approval needed):
  GET  /tools/get_case/{case_id}
  GET  /tools/list_cases_summary
  GET  /tools/list_assigned_cases
  GET  /tools/get_case_history/{case_id}
  POST /tools/search_protocol
  GET  /tools/get_similar_cases/{case_id}

WRITE surface — safely gated:
  POST /execute-approved-plan  <- preferred; verifies plan_hash from chatbot-service
  POST /tools/<write_tool>     <- direct write (plan_hash via X-Approved-Plan-Hash header)

All executions are audit-logged with request_id, case_id, approved_plan_hash.
"""
import json
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger

from .config import settings
from .database import get_db, close_db
from .auth import get_current_user, require_admin
from .tools import (
    # read
    tool_get_case,
    tool_list_cases_summary,
    tool_list_assigned_cases,
    tool_get_case_history,
    tool_search_protocol,
    tool_get_similar_cases,
    # write
    tool_add_checklist_item,
    tool_add_checklist_items,
    tool_update_checklist_item_status,
    tool_add_case_note,
    tool_update_case_status,
    tool_request_reassignment,
    tool_submit_review_request,
)
from .audit import audit_log


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("mcp-service starting up...")
    await get_db()
    yield
    await close_db()
    logger.info("mcp-service shut down.")


app = FastAPI(
    title="SCS MCP Service",
    description="Approval-gated tool gateway with read/write surface separation and full audit logging",
    version="2.0.0",
    lifespan=lifespan,
)

origins = [o.strip() for o in settings.allowed_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)


def _get_user(request: Request):
    return get_current_user(request)


def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-Id", str(uuid.uuid4()))


# ═══════════════════════════════════════════════════════════════════════════════
# READ TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/tools/get_case/{case_id}")
async def get_case(case_id: str, request: Request):
    user = _get_user(request)
    return await tool_get_case(case_id, user)


@app.get("/tools/list_cases_summary")
async def list_cases_summary(
    request: Request,
    category: Optional[str] = None,
    status: Optional[str] = None,
):
    user = _get_user(request)
    return await tool_list_cases_summary(user, category=category, status=status)


@app.get("/tools/list_assigned_cases")
async def list_assigned_cases(request: Request):
    user = _get_user(request)
    return await tool_list_assigned_cases(user)


@app.get("/tools/get_case_history/{case_id}")
async def get_case_history(case_id: str, request: Request):
    user = _get_user(request)
    return await tool_get_case_history(case_id, user)


@app.post("/tools/query_case_details")
async def query_case_details(request: Request):
    """POST endpoint for query_case_details tool (gets full case details)"""
    user = _get_user(request)
    body = await request.json()
    case_id = body.get("case_id")
    if not case_id:
        raise HTTPException(status_code=400, detail="case_id required")
    return await tool_get_case(case_id, user)


@app.post("/tools/query_similar_cases")
async def query_similar_cases_post(request: Request):
    """POST endpoint for query_similar_cases tool"""
    user = _get_user(request)
    body = await request.json()
    case_id = body.get("case_id")
    limit = body.get("limit", 5)
    if not case_id:
        raise HTTPException(status_code=400, detail="case_id required")
    return await tool_get_similar_cases(case_id, user, top_k=limit)


@app.post("/tools/query_instagram_data")
async def query_instagram_data(request: Request):
    """POST endpoint for query_instagram_data tool (stub for now)"""
    user = _get_user(request)
    body = await request.json()
    youth_handle = body.get("youth_handle")
    if not youth_handle:
        raise HTTPException(status_code=400, detail="youth_handle required")
    
    # TODO: Implement MongoDB query for Instagram scraper data
    return {
        "success": True,
        "message": "Instagram data query not yet fully implemented",
        "youth_handle": youth_handle,
        "note": "This tool will query the Instagram scraper MongoDB for activity patterns"
    }


class ProtocolSearchRequest(BaseModel):
    query: str


@app.post("/tools/search_protocol")
async def search_protocol(body: ProtocolSearchRequest, request: Request):
    user = _get_user(request)
    return await tool_search_protocol(body.query, user)


@app.get("/tools/get_similar_cases/{case_id}")
async def get_similar_cases(case_id: str, request: Request, top_k: int = 5):
    user = _get_user(request)
    return await tool_get_similar_cases(case_id, user, top_k=top_k)


# ═══════════════════════════════════════════════════════════════════════════════
# EXECUTE-APPROVED-PLAN  (the only safe entry point for writes)
# ═══════════════════════════════════════════════════════════════════════════════

class ExecutePlanRequest(BaseModel):
    plan_hash: str
    case_id: str


@app.post("/execute-approved-plan")
async def execute_approved_plan(body: ExecutePlanRequest, request: Request):
    """
    Approval gateway.

    Flow:
      1. Frontend sends plan_hash (returned by chatbot /chat) + case_id.
      2. We fetch the stored execution_plan from chatbot-service /pending-plan/{hash}.
      3. Execute each step IN ORDER using the appropriate write tool.
      4. Log every step with request_id + approved_plan_hash.
      5. Return step-by-step results.

    On any step failure the remaining steps are aborted and partial results returned.
    """
    user = _get_user(request)
    req_id = _request_id(request)

    # Fetch plan from chatbot-service
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(
                f"{settings.chatbot_service_url}/pending-plan/{body.plan_hash}",
                headers={"X-User-Id": user.user_id, "X-User-Role": user.role},
            )
            if r.status_code == 404:
                raise HTTPException(404, "Plan not found or already executed. Please regenerate.")
            if r.status_code != 200:
                raise HTTPException(502, f"Chatbot service error: {r.status_code}")
            plan_envelope = r.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(503, f"Cannot reach chatbot-service: {e}")

    execution_plan: list = plan_envelope.get("plan", [])
    if not execution_plan:
        return {"status": "no_steps", "results": []}

    case_id = body.case_id or plan_envelope.get("case_id", "")
    logger.info(
        f"[{req_id}] Executing approved plan hash={body.plan_hash} "
        f"case_id={case_id} steps={len(execution_plan)} actor={user.user_id}"
    )

    results: list = []
    write_kwargs = dict(request_id=req_id, approved_plan_hash=body.plan_hash)

    for step in execution_plan:
        tool_name = step.get("mcp_tool", "")
        args: dict = step.get("args", {})
        args.setdefault("case_id", case_id)

        step_result: dict = {}
        error: Optional[str] = None

        try:
            if tool_name == "add_checklist_item":
                step_result = await tool_add_checklist_item(
                    case_id=args["case_id"],
                    label=args.get("label", ""),
                    user=user,
                    is_mandatory=args.get("is_mandatory", False),
                    **write_kwargs,
                )
            elif tool_name == "add_checklist_items" or tool_name == "create_checklist_items":
                step_result = await tool_add_checklist_items(
                    case_id=args["case_id"],
                    items=args.get("items", []),
                    user=user,
                    **write_kwargs,
                )
            elif tool_name == "update_checklist_item_status":
                step_result = await tool_update_checklist_item_status(
                    case_id=args["case_id"],
                    checklist_item_id=int(args["checklist_item_id"]),
                    completed=args.get("completed", True),
                    comment=args.get("comment", "Updated via approved agent plan"),
                    user=user,
                    **write_kwargs,
                )
            elif tool_name == "add_case_note":
                step_result = await tool_add_case_note(
                    case_id=args["case_id"],
                    content=args.get("content", ""),
                    user=user,
                    note_type=args.get("note_type", "general"),
                    **write_kwargs,
                )
            elif tool_name == "update_case_status":
                step_result = await tool_update_case_status(
                    case_id=args["case_id"],
                    status=args["status"],
                    user=user,
                    **write_kwargs,
                )
            elif tool_name == "request_reassignment":
                step_result = await tool_request_reassignment(
                    case_id=args["case_id"],
                    reason=args.get("reason", ""),
                    user=user,
                    requested_to=args.get("requested_to"),
                    **write_kwargs,
                )
            elif tool_name == "submit_review_request":
                step_result = await tool_submit_review_request(
                    case_id=args["case_id"],
                    review_type=args.get("review_type", "general"),
                    reason=args.get("reason", ""),
                    user=user,
                    **write_kwargs,
                )
            else:
                error = f"Unknown tool: {tool_name}"
                logger.warning(f"[{req_id}] Unknown tool in plan: {tool_name}")

        except HTTPException as e:
            error = f"HTTP {e.status_code}: {e.detail}"
            logger.warning(f"[{req_id}] Step '{tool_name}' failed: {error}")
        except Exception as e:
            error = str(e)
            logger.error(f"[{req_id}] Step '{tool_name}' unexpected error: {e}")

        results.append({
            "step": step.get("step", len(results) + 1),
            "mcp_tool": tool_name,
            "result": step_result if not error else None,
            "error": error,
            "success": error is None and bool(step_result),
        })

        if error:
            logger.warning(f"[{req_id}] Aborting plan at step {step.get('step')}")
            break

    all_ok = all(r["success"] for r in results)
    logger.info(f"[{req_id}] Plan execution complete: {len(results)} steps, all_ok={all_ok}")

    # Best-effort: consume the plan so it cannot be reused
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.delete(
                f"{settings.chatbot_service_url}/pending-plan/{body.plan_hash}",
                headers={"X-User-Id": user.user_id, "X-User-Role": user.role},
            )
    except Exception:
        pass

    return {
        "status": "completed" if all_ok else "partial",
        "plan_hash": body.plan_hash,
        "request_id": req_id,
        "steps_executed": len(results),
        "all_succeeded": all_ok,
        "results": results,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# DIRECT WRITE ENDPOINTS  (plan_hash from X-Approved-Plan-Hash header)
# ═══════════════════════════════════════════════════════════════════════════════

class AddChecklistItemRequest(BaseModel):
    case_id: str
    label: str
    is_mandatory: bool = False


@app.post("/tools/add_checklist_item")
async def add_checklist_item(body: AddChecklistItemRequest, request: Request):
    user = _get_user(request)
    req_id = _request_id(request)
    plan_hash = request.headers.get("X-Approved-Plan-Hash", "")
    return await tool_add_checklist_item(
        body.case_id, body.label, user, body.is_mandatory,
        request_id=req_id, approved_plan_hash=plan_hash,
    )


class AddChecklistItemsRequest(BaseModel):
    case_id: str
    items: list[dict]


@app.post("/tools/add_checklist_items")
async def add_checklist_items(body: AddChecklistItemsRequest, request: Request):
    user = _get_user(request)
    req_id = _request_id(request)
    plan_hash = request.headers.get("X-Approved-Plan-Hash", "")
    return await tool_add_checklist_items(
        body.case_id, body.items, user,
        request_id=req_id, approved_plan_hash=plan_hash,
    )


class ChecklistStatusRequest(BaseModel):
    case_id: str
    checklist_item_id: int
    completed: bool
    comment: str


@app.post("/tools/update_checklist_item_status")
async def update_checklist_item_status(body: ChecklistStatusRequest, request: Request):
    user = _get_user(request)
    req_id = _request_id(request)
    plan_hash = request.headers.get("X-Approved-Plan-Hash", "")
    return await tool_update_checklist_item_status(
        body.case_id, body.checklist_item_id, body.completed, body.comment, user,
        request_id=req_id, approved_plan_hash=plan_hash,
    )


class CaseNoteRequest(BaseModel):
    case_id: str
    content: str
    note_type: str = "general"


@app.post("/tools/add_case_note")
async def add_case_note(body: CaseNoteRequest, request: Request):
    user = _get_user(request)
    req_id = _request_id(request)
    plan_hash = request.headers.get("X-Approved-Plan-Hash", "")
    return await tool_add_case_note(
        body.case_id, body.content, user, body.note_type,
        request_id=req_id, approved_plan_hash=plan_hash,
    )


class CaseStatusRequest(BaseModel):
    case_id: str
    status: str


@app.post("/tools/update_case_status")
async def update_case_status(body: CaseStatusRequest, request: Request):
    user = _get_user(request)
    req_id = _request_id(request)
    plan_hash = request.headers.get("X-Approved-Plan-Hash", "")
    return await tool_update_case_status(
        body.case_id, body.status, user,
        request_id=req_id, approved_plan_hash=plan_hash,
    )


class ReassignmentRequest(BaseModel):
    case_id: str
    reason: str
    requested_to: Optional[str] = None


@app.post("/tools/request_reassignment")
async def request_reassignment(body: ReassignmentRequest, request: Request):
    user = _get_user(request)
    req_id = _request_id(request)
    plan_hash = request.headers.get("X-Approved-Plan-Hash", "")
    return await tool_request_reassignment(
        body.case_id, body.reason, user, body.requested_to,
        request_id=req_id, approved_plan_hash=plan_hash,
    )


class ReviewRequest(BaseModel):
    case_id: str
    review_type: str  # escalation, closure, follow_up, general
    reason: str


@app.post("/tools/submit_review_request")
async def submit_review_request(body: ReviewRequest, request: Request):
    user = _get_user(request)
    req_id = _request_id(request)
    plan_hash = request.headers.get("X-Approved-Plan-Hash", "")
    return await tool_submit_review_request(
        body.case_id, body.review_type, body.reason, user,
        request_id=req_id, approved_plan_hash=plan_hash,
    )



# ═══════════════════════════════════════════════════════════════════════════════
# AUDIT LOG VIEWER  (Admin only)
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/audit-log")
async def get_audit_log(
    request: Request,
    limit: int = 50,
    case_id: Optional[str] = None,
    tool_name: Optional[str] = None,
    actor_id: Optional[str] = None,
    plan_hash: Optional[str] = None,
):
    require_admin(request)
    db = await get_db()

    audit_col = db['mcp_audit_log']
    
    # Build MongoDB query
    query: dict = {}
    if case_id:
        query["case_id"] = case_id
    if tool_name:
        query["tool_name"] = tool_name
    if actor_id:
        query["actor_id"] = actor_id
    if plan_hash:
        query["approved_plan_hash"] = plan_hash
    
    # Query with limit
    cursor = audit_col.find(query).sort("created_at", -1).limit(limit)
    rows = await cursor.to_list(length=limit)
    
    # Parse JSON fields and remove _id
    for r in rows:
        if "_id" in r:
            del r["_id"]
        for f in ("payload", "result"):
            if isinstance(r.get(f), str):
                try:
                    r[f] = json.loads(r[f])
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
            "add_checklist_item", "update_checklist_item_status",
            "add_case_note", "update_case_status",
            "request_reassignment", "submit_review_request",
        ],
        "approval_gateway": "/execute-approved-plan",
        "note": "Write tools should only be called via /execute-approved-plan with a plan_hash from chatbot-service.",
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "mcp-service", "version": "2.0.0"}
