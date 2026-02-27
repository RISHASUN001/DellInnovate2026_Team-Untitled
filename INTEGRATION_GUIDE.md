# Integration Guide for Analysis, Chatbot, Image, MCP, and Case Services

## Overview
Your service will connect to the platform via the API Gateway and/or directly to the secure-data-service (for internal data access). All requests must be authenticated using JWTs with the correct `service` and `scope` claims.

---

## 1. Authentication
- Obtain a JWT from the Auth Service (via OAuth or service credentials).
- JWT must include:
  - `service`: your service name (e.g., `analysis-service`, `chatbot-service`, etc.)
  - `scope`: one of `read:personal_data`, `analyze:personal_data`, or `write:personal_data` as appropriate.

---

## 2. API Gateway Endpoints

| Service         | Endpoint           | Method | Description                |
|-----------------|--------------------|--------|----------------------------|
| Analysis        | `/analyze`         | GET    | Proxy to analysis-service  |
| Chatbot         | `/chatbot`         | POST   | Proxy to chatbot-service   |
| Image           | `/image`           | POST   | Proxy to image-service     |
| MCP             | `/mcp`             | POST   | Proxy to mcp-service       |
| Case            | `/case`            | POST   | Proxy to case-service      |

- All endpoints require `Authorization: Bearer <JWT>` header.
- The gateway will validate your token and forward the request.

---

## 3. Secure Data Service Endpoints

- **Store Data:**
  - `POST /internal/store` (internal, for scraper-service)
  - Requires `service: scraper-service`, `scope: write:personal_data`

- **Get Data:**
  - `GET /internal/data`
  - Requires `service` in `[analysis-service, chatbot-service, image-service, mcp-service, case-service]`
  - Requires `scope` in `[read:personal_data, analyze:personal_data]`
  - Returns all stored data (optionally filter on your end)

---

## 4. Example: Accessing Data

```python
import requests
headers = {
    "Authorization": "Bearer <YOUR_JWT>"
}
resp = requests.get("http://secure-data-service:8000/internal/data", headers=headers)
print(resp.json())
```

---

## 5. Error Handling
- 401 Unauthorized: Invalid or missing JWT
- 403 Forbidden: JWT does not have correct service or scope
- 500 Internal Server Error: Unexpected backend error

---

## 6. What You Need To Do
1. Implement OAuth/JWT authentication in your service (use the Auth Service).
2. Use the API Gateway endpoints for all cross-service calls.
3. For direct data access, use `/internal/data` with a valid JWT.
4. Always include the correct `service` and `scope` claims in your JWT.
5. Handle error responses as described above.

---

## 7. Example JWT Payload
```json
{
  "service": "analysis-service",
  "scope": "read:personal_data",
  "exp": 1950000000
}
```

---

## 8. Contact
For questions or onboarding help, contact the backend team.
