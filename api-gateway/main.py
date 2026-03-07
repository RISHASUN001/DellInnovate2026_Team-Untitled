# ...existing code...
from fastapi import FastAPI, Request, HTTPException, status, Body
import httpx
import os

app = FastAPI()

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000")
SCRAPER_SERVICE_URL = os.getenv("SCRAPER_SERVICE_URL", "http://scraper-service:8000/scrape")

ANALYSIS_SERVICE_URL = os.getenv("ANALYSIS_SERVICE_URL", "http://analysis-service:8000/analyze")
CHATBOT_SERVICE_URL = os.getenv("CHATBOT_SERVICE_URL", "http://chatbot-service:8000/chat")
IMAGE_SERVICE_URL = os.getenv("IMAGE_SERVICE_URL", "http://image-service:8000/process")
MCP_SERVICE_URL = os.getenv("MCP_SERVICE_URL", "http://mcp-service:8000/ops")
CASE_SERVICE_URL = os.getenv("CASE_SERVICE_URL", "http://case-service:8000/case")

async def validate_token(request: Request):
    token = request.headers.get("Authorization")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{AUTH_SERVICE_URL}/me", headers={"Authorization": token})
        if resp.status_code != 200:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        return resp.json()

# Protected route: proxy to scraper-service
@app.post("/scrape")
async def scrape(request: Request):
    await validate_token(request)
    data = await request.json()
    async with httpx.AsyncClient() as client:
        resp = await client.post(SCRAPER_SERVICE_URL, json=data)
    return resp.json()


# Proxy to analysis-service
@app.get("/analyze")
async def analyze(request: Request):
    await validate_token(request)
    async with httpx.AsyncClient() as client:
        resp = await client.get(ANALYSIS_SERVICE_URL)
    return resp.json()

# Proxy to chatbot-service
@app.post("/chatbot")
async def chatbot(request: Request):
    await validate_token(request)
    data = await request.json()
    async with httpx.AsyncClient() as client:
        resp = await client.post(CHATBOT_SERVICE_URL, json=data)
    return resp.json()

# Proxy to image-service
@app.post("/image")
async def image(request: Request):
    await validate_token(request)
    data = await request.json()
    async with httpx.AsyncClient() as client:
        resp = await client.post(IMAGE_SERVICE_URL, json=data)
    return resp.json()

# Proxy to mcp-service
@app.post("/mcp")
async def mcp(request: Request):
    await validate_token(request)
    data = await request.json()
    async with httpx.AsyncClient() as client:
        resp = await client.post(MCP_SERVICE_URL, json=data)
    return resp.json()

# Proxy to case-service
@app.post("/case")
async def case(request: Request):
    await validate_token(request)
    data = await request.json()
    async with httpx.AsyncClient() as client:
        resp = await client.post(CASE_SERVICE_URL, json=data)
    return resp.json()

# Auth login redirect
from fastapi.responses import RedirectResponse

@app.get("/login")
async def login():
    return RedirectResponse(f"{AUTH_SERVICE_URL}/login")

# Auth callback proxy (optional, for frontend integration)
@app.get("/callback")
async def callback(code: str):
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{AUTH_SERVICE_URL}/callback", params={"code": code})
    return resp.json()

# Terminal-friendly endpoint: proxy OAuth code exchange
@app.post("/token")
async def token(code: str = Body(..., embed=True)):
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{AUTH_SERVICE_URL}/token", json={"code": code})
    return resp.json()
