# Secure Instagram Scraper Microservices Setup

## Prerequisites
- Docker & Docker Compose
- Python 3.11 (for local testing)
- [Scrapfly.io](https://scrapfly.io/) API key
- OpenSSL (for key generation)

## Folder Structure
```
project-root/
  scraper-service/
    app.py
    instagram.py
    jwt_utils.py
    requirements.txt
    Dockerfile
    .env.example
  secure-data-service/
    app.py
    auth.py
    database.py
    models.py
    requirements.txt
    Dockerfile
    .env.example
  secrets/
    private_key.pem
    public_key.pem
  docker-compose.yml
  README.md
```

## 1. Generate RSA Keys
```sh
# In project root:
mkdir -p secrets
openssl genrsa -out secrets/private_key.pem 2048
openssl rsa -in secrets/private_key.pem -pubout -out secrets/public_key.pem
```

## 2. Set Environment Variables
- Copy `.env.example` to `.env` in both `scraper-service/` and `secure-data-service/`.
- Fill in your `SCRAPFLY_KEY` in `scraper-service/.env`.

## 3. Build and Run All Services
```sh
docker-compose up --build
```

## 4. Check MongoDB Data
```sh
docker-compose exec mongodb mongo
# In the mongo shell:
use scraperdb
db.personal_data.find().pretty()
```

## 5. Test Secure Data Service Endpoint
### Valid JWT Example
```sh
curl -X POST http://localhost:8000/internal/store \
  -H "Authorization: Bearer <valid_jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{"source":"scrapy","timestamp":"2026-02-27T12:00:00Z","payload":{}}'
```
### Invalid JWT Example
```sh
curl -X POST http://localhost:8000/internal/store \
  -H "Authorization: Bearer invalidtoken" \
  -H "Content-Type: application/json" \
  -d '{"source":"scrapy","timestamp":"2026-02-27T12:00:00Z","payload":{}}'
```

## 6. Troubleshooting
- Ensure `SCRAPFLY_KEY` is valid and not rate-limited.
- Ensure secrets are mounted and not inside Docker images.
- MongoDB is not exposed to host; only accessible by services.
- Logs do not contain personal data.

## 7. Extending
- Add more endpoints to `secure-data-service` for future analysis or RBAC.
- Add unit/integration tests as needed.

---

**For any issues, check logs with:**
```sh
docker-compose logs scraper-service
# or
# docker-compose logs secure-data-service
```
