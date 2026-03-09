# Google OAuth Setup for SCS Dashboard

## Problem
Browser shows "can't reach this page" error for `auth-service` after Google OAuth redirect.

## Root Cause
Google OAuth Console doesn't have `http://localhost:8001/callback` registered as an authorized redirect URI.

## Solution

### 1. Update Google Cloud Console

1. Go to: https://console.cloud.google.com/apis/credentials
2. Select your OAuth 2.0 Client ID: `5160573405-efm2lesqgp1r6vfis1igu75575khp2fr.apps.googleusercontent.com`
3. Under **Authorized redirect URIs**, add:
   ```
   http://localhost:8001/callback
   ```
4. Click **Save**

### 2. Restart Auth Service (if needed)

```powershell
# Stop the Docker container
docker-compose -f docker-compose.auth.yml down

# Start it again
docker-compose -f docker-compose.auth.yml --env-file .env.auth up -d
```

### 3. Test OAuth Flow

1. Open: http://localhost:5174
2. Click: "Sign in with Google OAuth"
3. Complete Google consent
4. Should redirect to: `http://localhost:8001/callback?code=...`
5. Then redirect back to frontend with token

## Current Configuration

- **Auth Service**: http://localhost:8001 (Docker)
- **API Gateway**: http://localhost:8010 (Local)
- **Frontend**: http://localhost:5174 (Local)

## OAuth Flow

```
Frontend (5174)
  ↓ Click "Sign in with Google"
API Gateway (8010/login)
  ↓ Redirect to
Auth Service (8001/login)
  ↓ Redirect to
Google OAuth Consent
  ↓ User approves
Google redirects to: http://localhost:8001/callback?code=xxx
  ↓ Auth service exchanges code for token
Auth Service returns to API Gateway
  ↓ API Gateway returns to Frontend
Frontend receives token and user info
```

## Verification

Check auth service logs:
```powershell
docker logs dellinnovate2026_team-untitled-auth-service-1
```

Test callback directly:
```powershell
# Should return {"tokens": {...}, "userinfo": {...}}
curl "http://localhost:8001/callback?code=FAKE_CODE"
```
