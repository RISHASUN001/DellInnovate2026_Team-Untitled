# ...existing code...
import os
from fastapi import FastAPI, Request, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
import httpx
from urllib.parse import urlencode, unquote
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

raw_cors_origins = os.getenv(
    "CORS_ALLOW_ORIGINS",
    "http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174",
)
cors_origins = [origin.strip() for origin in raw_cors_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


def missing_oauth_config() -> list[str]:
    missing = []
    if not OAUTH_AUTHORIZE_URL:
        missing.append("OAUTH_AUTHORIZE_URL")
    if not OAUTH_TOKEN_URL:
        missing.append("OAUTH_TOKEN_URL")
    if not OAUTH_REDIRECT_URI:
        missing.append("OAUTH_REDIRECT_URI")
    if not OAUTH_CLIENT_ID:
        missing.append("OAUTH_CLIENT_ID")
    if not OAUTH_CLIENT_SECRET:
        missing.append("OAUTH_CLIENT_SECRET")
    return missing

# Terminal-friendly endpoint: exchange OAuth code for tokens
@app.post("/token")
async def token(code: str = Body(..., embed=True)):
    missing = missing_oauth_config()
    if missing:
        return JSONResponse(
            status_code=500,
            content={
                "error": "OAuth configuration is incomplete",
                "details": {"missing": missing},
            },
        )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
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

            try:
                tokens = token_resp.json()
            except ValueError:
                return JSONResponse(
                    status_code=502,
                    content={"error": "Token endpoint returned non-JSON response", "details": token_resp.text},
                )

            access_token = tokens.get("access_token")
            if not access_token:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Token exchange did not return access_token", "details": tokens},
                )

            # Fetch user info
            userinfo_resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            if userinfo_resp.status_code != 200:
                return JSONResponse(status_code=400, content={"error": "Userinfo fetch failed", "details": userinfo_resp.text})

            try:
                userinfo = userinfo_resp.json()
            except ValueError:
                return JSONResponse(
                    status_code=502,
                    content={"error": "Userinfo endpoint returned non-JSON response", "details": userinfo_resp.text},
                )
    except httpx.RequestError as exc:
        return JSONResponse(
            status_code=502,
            content={"error": "Unable to reach OAuth provider", "details": str(exc)},
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": "Unexpected auth-service error", "details": str(exc)},
        )

    return {"tokens": tokens, "userinfo": userinfo}

@app.get("/login")
def login(frontend_redirect: str | None = None, mode: str | None = None):
    missing = missing_oauth_config()
    if missing:
        return JSONResponse(
            status_code=500,
            content={
                "error": "OAuth configuration is incomplete",
                "details": {"missing": missing},
            },
        )

    # Encode state to pass through OAuth and back to callback
    # Format: "redirect_url|mode" where mode can be "json" or empty
    state_data = {
        "redirect": frontend_redirect or FRONTEND_REDIRECT_URL,
        "mode": mode or "web"
    }
    state = urlencode(state_data)
    
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
    # Parse state parameter (contains redirect URL and mode)
    state_data = {}
    if state:
        try:
            from urllib.parse import parse_qs
            parsed = parse_qs(unquote(state))
            # parse_qs returns lists, get first value
            state_data = {k: v[0] if isinstance(v, list) and v else v for k, v in parsed.items()}
        except Exception:
            state_data = {"redirect": state, "mode": "web"}
    
    if not state_data:
        state_data = {"redirect": FRONTEND_REDIRECT_URL, "mode": "web"}
    
    redirect_base = state_data.get("redirect", FRONTEND_REDIRECT_URL)
    mode = state_data.get("mode", "web")
    
    # Validate redirect URL
    if not redirect_base.startswith("http://") and not redirect_base.startswith("https://"):
        redirect_base = FRONTEND_REDIRECT_URL

    # For CLI/script mode, return JSON with authorization code
    if mode == "json":
        return JSONResponse({
            "code": code,
            "message": "Authorization code received. Exchange it for a token using POST /token"
        })
    
    # For web mode, redirect to frontend with code
    redirect_url = f"{redirect_base}?{urlencode({'code': code})}"
    return RedirectResponse(redirect_url)

# Example protected endpoint (for API Gateway to validate tokens)
@app.get("/me")
async def me(request: Request):
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    bearer_token = auth.split(" ", 1)[1]

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            # Path 1: OAuth access token
            resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {bearer_token}"},
            )
            if resp.status_code == 200:
                return resp.json()

            # Path 2: JWT id_token
            tokeninfo_resp = await client.get(
                GOOGLE_TOKENINFO_URL,
                params={"id_token": bearer_token},
            )
            if tokeninfo_resp.status_code == 200:
                return tokeninfo_resp.json()
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Unable to reach Google token validation endpoints: {exc}") from exc

    raise HTTPException(status_code=401, detail="Invalid or expired token")
