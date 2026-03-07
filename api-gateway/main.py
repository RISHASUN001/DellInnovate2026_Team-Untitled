import os
from typing import Any, Dict, List, Optional

import httpx
from fastapi import Body, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

app = FastAPI(title="SCS API Gateway", version="1.1.0")

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000")
SCRAPER_SERVICE_URL = os.getenv("SCRAPER_SERVICE_URL", "http://scraper-service:8000/scrape")
ANALYSIS_SERVICE_URL = os.getenv(
    "ANALYSIS_SERVICE_URL",
    "http://backend:8000/api/unified-pipeline/analyze-user",
)
CHATBOT_SERVICE_URL = os.getenv("CHATBOT_SERVICE_URL", "http://chatbot-service:8000/chat")
IMAGE_SERVICE_URL = os.getenv("IMAGE_SERVICE_URL", "http://image-service:8000/run")
MCP_SERVICE_URL = os.getenv("MCP_SERVICE_URL", "http://mcp-service:8000/ops")
CASE_SERVICE_URL = os.getenv("CASE_SERVICE_URL", "http://case-service:8000/case")


class AnalyzeRequest(BaseModel):
    username: str
    scrape_comments: bool = False
    export_csv: bool = True


class WorkflowRequest(BaseModel):
    username: str
    scrape_payload: Dict[str, Any] = Field(default_factory=dict)
    analysis_payload: Dict[str, Any] = Field(default_factory=dict)
    include_chatbot: bool = False
    chatbot_message: Optional[str] = None
    case_info: Optional[Dict[str, Any]] = None
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)
    execute_tools: bool = True


async def validate_token(request: Request) -> Dict[str, Any]:
    token = request.headers.get("Authorization")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{AUTH_SERVICE_URL}/me",
            headers={"Authorization": token},
        )
        if resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        return resp.json()


async def _call_service(
    method: str,
    url: str,
    payload: Optional[Dict[str, Any]] = None,
    auth_header: Optional[str] = None,
) -> Dict[str, Any]:
    headers: Dict[str, str] = {}
    if auth_header:
        headers["Authorization"] = auth_header

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.request(method, url, json=payload, headers=headers)

    try:
        data = response.json()
    except ValueError:
        data = {"raw": response.text}

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail={
                "service_url": url,
                "status_code": response.status_code,
                "response": data,
            },
        )

    return data


@app.post("/scrape")
async def scrape(request: Request):
    await validate_token(request)
    payload = await request.json()
    return await _call_service("POST", SCRAPER_SERVICE_URL, payload)


@app.post("/analyze")
async def analyze(request: Request, body: AnalyzeRequest):
    await validate_token(request)
    return await _call_service("POST", ANALYSIS_SERVICE_URL, body.model_dump())


@app.get("/analyze")
async def analyze_get(request: Request, username: str):
    await validate_token(request)
    payload = {
        "username": username,
        "scrape_comments": False,
        "export_csv": True,
    }
    return await _call_service("POST", ANALYSIS_SERVICE_URL, payload)


@app.post("/chatbot")
async def chatbot(request: Request):
    await validate_token(request)
    payload = await request.json()
    return await _call_service(
        "POST",
        CHATBOT_SERVICE_URL,
        payload,
        auth_header=request.headers.get("Authorization"),
    )


@app.post("/image")
async def image(request: Request):
    await validate_token(request)
    payload = await request.json()
    return await _call_service("POST", IMAGE_SERVICE_URL, payload)


@app.post("/mcp")
async def mcp(request: Request):
    await validate_token(request)
    payload = await request.json()
    return await _call_service(
        "POST",
        MCP_SERVICE_URL,
        payload,
        auth_header=request.headers.get("Authorization"),
    )


@app.post("/case")
async def case(request: Request):
    await validate_token(request)
    payload = await request.json()
    return await _call_service(
        "POST",
        CASE_SERVICE_URL,
        payload,
        auth_header=request.headers.get("Authorization"),
    )


@app.post("/workflow/run")
async def workflow_run(request: Request, body: WorkflowRequest):
    """End-to-end workflow:
    1) Validate Google OAuth token
    2) Run scraper service
    3) Run NLP analysis service
    4) Optionally run chatbot with analysis context
    """
    user = await validate_token(request)
    auth_header = request.headers.get("Authorization")

    scrape_payload = {"username": body.username}
    scrape_payload.update(body.scrape_payload)

    analysis_payload = {
        "username": body.username,
        "scrape_comments": True,
        "export_csv": True,
    }
    analysis_payload.update(body.analysis_payload)

    scrape_result = await _call_service("POST", SCRAPER_SERVICE_URL, scrape_payload)
    analysis_result = await _call_service("POST", ANALYSIS_SERVICE_URL, analysis_payload)

    chatbot_result: Optional[Dict[str, Any]] = None
    if body.include_chatbot:
        chatbot_payload = {
            "message": body.chatbot_message
            or f"Review analysis findings for @{body.username} and suggest next actions.",
            "case_info": body.case_info
            or {
                "code": body.username,
                "username": body.username,
                "analysis_summary": analysis_result,
            },
            "conversation_history": body.conversation_history,
            "execute_tools": body.execute_tools,
        }
        chatbot_result = await _call_service(
            "POST",
            CHATBOT_SERVICE_URL,
            chatbot_payload,
            auth_header=auth_header,
        )

    return {
        "status": "ok",
        "flow": ["oauth", "scrape", "analysis", "chatbot" if body.include_chatbot else "chatbot_skipped"],
        "user": user,
        "scrape": scrape_result,
        "analysis": analysis_result,
        "chatbot": chatbot_result,
    }


@app.get("/login")
async def login(request: Request, frontend_redirect: str | None = Query(default=None)):
    resolved_frontend = frontend_redirect
    if not resolved_frontend:
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")
        if origin:
            resolved_frontend = origin
        elif referer and referer.startswith("http"):
            try:
                from urllib.parse import urlparse

                parsed = urlparse(referer)
                resolved_frontend = f"{parsed.scheme}://{parsed.netloc}"
            except Exception:
                resolved_frontend = None

    if resolved_frontend:
        encoded = httpx.QueryParams({"frontend_redirect": resolved_frontend})
        return RedirectResponse(f"{AUTH_SERVICE_URL}/login?{encoded}")

    return RedirectResponse(f"{AUTH_SERVICE_URL}/login")


@app.get("/callback")
async def callback(code: str):
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{AUTH_SERVICE_URL}/callback", params={"code": code})
    return resp.json()


@app.post("/token")
async def token(code: str = Body(..., embed=True)):
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{AUTH_SERVICE_URL}/token", json={"code": code})
    try:
        content = resp.json()
    except ValueError:
        content = {"error": "Invalid response from auth-service", "details": resp.text}

    return JSONResponse(status_code=resp.status_code, content=content)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "api-gateway",
        "services": {
            "auth": AUTH_SERVICE_URL,
            "scraper": SCRAPER_SERVICE_URL,
            "analysis": ANALYSIS_SERVICE_URL,
            "chatbot": CHATBOT_SERVICE_URL,
            "image": IMAGE_SERVICE_URL,
            "mcp": MCP_SERVICE_URL,
            "case": CASE_SERVICE_URL,
        },
    }
