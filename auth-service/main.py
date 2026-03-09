# ...existing code...
import os
from fastapi import FastAPI, Request, HTTPException, Body
from fastapi.responses import RedirectResponse, JSONResponse
import httpx
from urllib.parse import urlencode

app = FastAPI()


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "auth-service"}


OAUTH_AUTHORIZE_URL = os.getenv("OAUTH_AUTHORIZE_URL")
OAUTH_TOKEN_URL = os.getenv("OAUTH_TOKEN_URL")
OAUTH_REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI")
FRONTEND_REDIRECT_URL = os.getenv("FRONTEND_REDIRECT_URL", "http://localhost:5174")

def read_secret(secret_path):
    try:
        with open(secret_path, 'r') as f:
            return f.read().strip()
    except Exception:
        return None

OAUTH_CLIENT_ID = read_secret(os.getenv("OAUTH_CLIENT_ID_FILE", "/run/secrets/oauth_client_id")) or os.getenv("OAUTH_CLIENT_ID")
OAUTH_CLIENT_SECRET = read_secret(os.getenv("OAUTH_CLIENT_SECRET_FILE", "/run/secrets/oauth_client_secret")) or os.getenv("OAUTH_CLIENT_SECRET")

GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

# Terminal-friendly endpoint: exchange OAuth code for tokens
@app.post("/token")
async def token(code: str = Body(..., embed=True)):
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            OAUTH_TOKEN_URL,
            data={
                "code": code,
                "client_id": OAUTH_CLIENT_ID,
                "client_secret": OAUTH_CLIENT_SECRET,
                "redirect_uri": OAUTH_REDIRECT_URI,
                "grant_type": "authorization_code"
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        if token_resp.status_code != 200:
            return JSONResponse(status_code=400, content={"error": "Token exchange failed", "details": token_resp.text})
        tokens = token_resp.json()
        # Fetch user info
        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )
        if userinfo_resp.status_code != 200:
            return JSONResponse(status_code=400, content={"error": "Userinfo fetch failed", "details": userinfo_resp.text})
        userinfo = userinfo_resp.json()
    return {"tokens": tokens, "userinfo": userinfo}

@app.get("/login")
def login(frontend_redirect: str | None = None):
    state = frontend_redirect or FRONTEND_REDIRECT_URL
    params = {
        "response_type": "code",
        "client_id": OAUTH_CLIENT_ID,
        "redirect_uri": OAUTH_REDIRECT_URI,
        "scope": "openid profile email",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    url = f"{OAUTH_AUTHORIZE_URL}?{urlencode(params)}"
    return RedirectResponse(url)

@app.get("/callback")
async def callback(code: str, state: str | None = None):
    redirect_base = state or FRONTEND_REDIRECT_URL
    if not redirect_base.startswith("http://") and not redirect_base.startswith("https://"):
        redirect_base = FRONTEND_REDIRECT_URL

    redirect_url = f"{redirect_base}?{urlencode({'code': code})}"
    return RedirectResponse(redirect_url)

# Example protected endpoint (for API Gateway to validate tokens)
@app.get("/me")
async def me(request: Request):
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    access_token = auth.split(" ", 1)[1]
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return resp.json()
