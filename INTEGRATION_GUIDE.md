
# Integration Guide: Secure Microservices Setup

This guide explains how to securely connect, authenticate, and manage secrets for all backend services (analysis, chatbot, image, mcp, case, etc.) in your platform.

---

## Step 1: Secure Secrets Management (Docker Secrets)

**Never commit real secrets to Git.**

1. All sensitive credentials (OAuth client IDs, API keys, private keys, etc.) must be stored as Docker secrets in the `secrets/` directory.
2. The `secrets/` directory is excluded from version control via `.gitignore`.
3. Each secret is a file containing only the secret value (no extra whitespace).
4. See `secrets/README.md` for required secrets and example templates.

**Example:**
```
secrets/oauth_client_id
secrets/oauth_client_secret
secrets/private_key.pem
secrets/public_key.pem
secrets/scrapfly_key
```

---

## Step 2: Configure Docker Compose

1. In `docker-compose.yml`, each service mounts only the secrets it needs:
   ```yaml
   services:
     auth-service:
       secrets:
         - oauth_client_id
         - oauth_client_secret
     scraper-service:
       secrets:
         - private_key.pem
         - scrapfly_key
   secrets:
     oauth_client_id:
       file: ./secrets/oauth_client_id
     # ...
   ```
2. No secrets are set as environment variables or in `.env` files.

---

## Step 3: Access Secrets in Code

In your service code, read secrets from `/run/secrets/<secret_name>`:

```python
def read_secret(secret_name):
    with open(f'/run/secrets/{secret_name}', 'r') as f:
        return f.read().strip()

CLIENT_ID = read_secret('oauth_client_id')
CLIENT_SECRET = read_secret('oauth_client_secret')
```

---

## Step 4: Authentication & JWTs

1. **User Authentication:**
   - Users log in via Google OAuth (handled by auth-service).
   - Auth-service exchanges the code for a JWT.
2. **Service Authentication:**
   - Each backend service authenticates to auth-service using its client ID/secret (from Docker secrets) to obtain a JWT.
   - JWTs must include:
     - `service`: your service name (e.g., `analysis-service`)
     - `scope`: e.g., `read:personal_data`, `analyze:personal_data`, or `write:personal_data`
   - JWTs are used in the `Authorization: Bearer <JWT>` header for all API calls.

---

## Step 5: API Gateway Endpoints

| Service   | Endpoint     | Method | Description                |
|-----------|--------------|--------|----------------------------|
| Analysis  | `/analyze`   | GET    | Proxy to analysis-service  |
| Chatbot   | `/chatbot`   | POST   | Proxy to chatbot-service   |
| Image     | `/image`     | POST   | Proxy to image-service     |
| MCP       | `/mcp`       | POST   | Proxy to mcp-service       |
| Case      | `/case`      | POST   | Proxy to case-service      |

All endpoints require a valid JWT in the `Authorization` header. The gateway validates and forwards requests.

---

## Step 6: Secure Data Service Endpoints

- **Store Data:**
  - `POST /internal/store` (for scraper-service)
  - Requires `service: scraper-service`, `scope: write:personal_data`
- **Get Data:**
  - `GET /internal/data`
  - Requires `service` in `[analysis-service, chatbot-service, image-service, mcp-service, case-service]`
  - Requires `scope` in `[read:personal_data, analyze:personal_data]`
  - Returns all stored data (optionally filter on your end)

---

## Step 7: Example – Accessing Data

```python
import requests
headers = {
    "Authorization": "Bearer <YOUR_JWT>"
}
resp = requests.get("http://secure-data-service:8000/internal/data", headers=headers)
print(resp.json())
```

---

## Step 8: Error Handling

- 401 Unauthorized: Invalid or missing JWT
- 403 Forbidden: JWT does not have correct service or scope
- 500 Internal Server Error: Unexpected backend error

---

## Step 9: What You Need To Do

1. **Create all required secret files** in `secrets/` (see `secrets/README.md`).
2. **Never commit real secrets** – use `.gitignore` and share secrets securely.
3. **Configure Docker Compose** to mount secrets for each service.
4. **Update your service code** to read secrets from `/run/secrets/`.
5. **Authenticate to auth-service** to obtain JWTs for all API calls.
6. **Use API Gateway endpoints** for all cross-service communication.
7. **Handle errors** as described above.

---

## Step 10: Example JWT Payload
```json
{
  "service": "analysis-service",
  "scope": "read:personal_data",
  "exp": 1950000000
}
```

---

## Step 11: Contact
For questions or onboarding help, contact the backend team.
