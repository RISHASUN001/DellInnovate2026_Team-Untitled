

import os
import logging
import asyncio
import httpx
from jwt_utils import generate_jwt
from instagram import scrape_user
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "scraper-service"}


SECURE_DATA_SERVICE_URL = os.getenv('SECURE_DATA_SERVICE_URL')
PRIVATE_KEY_PATH = os.getenv('PRIVATE_KEY_PATH')
print(f"Loaded config: SECURE_DATA_SERVICE_URL={SECURE_DATA_SERVICE_URL}, PRIVATE_KEY_PATH={PRIVATE_KEY_PATH}")

def read_secret(secret_path):
    try:
        with open(secret_path, 'r') as f:
            return f.read().strip()
    except Exception:
        return None

SCRAPFLY_KEY = os.getenv('SCRAPFLY_KEY')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('scraper-service')

RETRY_LIMIT = 3

async def fetch_and_send():
    username = os.getenv('SCRAPER_USERNAME', 'chrishemsworth')
    logger.info(f'Starting scrape for user: {username}')
    data = await scrape_user(username)
    payload = {
        'source': 'scrapy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'payload': data
    }
    jwt_token = generate_jwt(PRIVATE_KEY_PATH)
    headers = {'Authorization': f'Bearer {jwt_token}'}
    for attempt in range(RETRY_LIMIT):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f'{SECURE_DATA_SERVICE_URL}/internal/store', json=payload, headers=headers)
            if resp.status_code == 200:
                logger.info('Data stored successfully, record_id: %s', resp.json().get('record_id'))
                return resp.json()
            elif resp.status_code in (401, 403):
                logger.error('Authentication failed: %s', resp.text)
                break
            else:
                logger.warning('Failed attempt %d: %s', attempt+1, resp.text)
        except Exception as e:
            logger.error('Exception on attempt %d: %s', attempt+1, str(e))
    logger.error('Failed to store data after retries')
    return None


# FastAPI endpoint to trigger scrape
@app.post("/scrape")
async def scrape_endpoint(request: Request):
    body = await request.json()
    username = body.get("username", os.getenv('SCRAPER_USERNAME', 'chrishemsworth'))
    logger.info(f'Starting scrape for user: {username}')
    data = await scrape_user(username)
    payload = {
        'source': 'scrapy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'payload': data
    }
    jwt_token = generate_jwt(PRIVATE_KEY_PATH)
    headers = {'Authorization': f'Bearer {jwt_token}'}
    for attempt in range(RETRY_LIMIT):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f'{SECURE_DATA_SERVICE_URL}/internal/store', json=payload, headers=headers)
            if resp.status_code == 200:
                logger.info('Data stored successfully, record_id: %s', resp.json().get('record_id'))
                return JSONResponse(content={"status": "success", "record_id": resp.json().get('record_id')})
            elif resp.status_code in (401, 403):
                logger.error('Authentication failed: %s', resp.text)
                return JSONResponse(status_code=resp.status_code, content={"error": "Authentication failed", "details": resp.text})
            else:
                logger.warning('Failed attempt %d: %s', attempt+1, resp.text)
        except Exception as e:
            logger.error('Exception on attempt %d: %s', attempt+1, str(e))
    logger.error('Failed to store data after retries')
    return JSONResponse(status_code=500, content={"error": "Failed to store data after retries"})
