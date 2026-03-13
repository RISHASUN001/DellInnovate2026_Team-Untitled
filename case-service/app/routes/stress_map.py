"""
Stress Map caching routes for Singapore Stress Heatmap
- GET /stress-map: Returns cached stress map data from MongoDB
- POST /stress-map/refresh: Calls webhook and updates cached data
"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import httpx
from loguru import logger
from ..database import get_db
import asyncio

router = APIRouter(prefix="/stress-map", tags=["stress-map"])

WEBHOOK_URL = "https://rishikamehta.app.n8n.cloud/webhook/live-stress-map"
COLLECTION_NAME = "stress_map_cache"

# Add CORS headers to all responses
async def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@router.options("")
@router.options("/refresh")
async def options_handler():
    """Handle CORS preflight requests"""
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
    )

@router.get("")
async def get_cached_stress_map():
    """
    Get the most recently cached stress map data from MongoDB.
    """
    try:
        db = await get_db()
        cache_col = db[COLLECTION_NAME]
        
        # Get the most recent cache entry
        cached = await cache_col.find_one(
            {},
            sort=[("cached_at", -1)]
        )
        
        if not cached:
            response = JSONResponse({
                "cached": False,
                "message": "No cached data available. Click refresh to fetch data.",
                "data": None
            })
            return await add_cors_headers(response)
        
        # Remove MongoDB _id field
        if "_id" in cached:
            del cached["_id"]
        
        response = JSONResponse({
            "cached": True,
            "cached_at": cached.get("cached_at"),
            "data": cached.get("data")
        })
        return await add_cors_headers(response)
        
    except Exception as e:
        logger.error(f"Error getting cached stress map: {e}")
        response = JSONResponse(
            {"error": str(e)},
            status_code=500
        )
        return await add_cors_headers(response)


@router.post("/refresh")
async def refresh_stress_map():
    """
    Fetch fresh stress map data from the webhook and cache it in MongoDB.
    Returns the newly fetched data, or cached data if webhook fails.
    """
    try:
        db = await get_db()
        cache_col = db[COLLECTION_NAME]
        
        # Call the webhook with proper timeout and headers
        logger.info(f"Calling webhook: {WEBHOOK_URL}")
        webhook_success = False
        
        try:
            async with httpx.AsyncClient(timeout=1000.0) as client:
                webhook_response = await client.get(
                    WEBHOOK_URL,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "StressMap-Backend/1.0"
                    }
                )
                logger.info(f"Webhook response status: {webhook_response.status_code}")
                webhook_response.raise_for_status()
                result = webhook_response.json()
                webhook_success = True
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error from webhook: {e.response.status_code} - {e.response.text[:200]}")
        except httpx.TimeoutException as e:
            logger.warning(f"Timeout while fetching stress map data from webhook: {e}")
        except Exception as e:
            logger.warning(f"Failed to call webhook: {e}")
        
        # If webhook failed, try to return cached data
        if not webhook_success:
            logger.info("Webhook failed, attempting to return cached data")
            cached = await cache_col.find_one({}, sort=[("cached_at", -1)])
            if cached:
                if "_id" in cached:
                    del cached["_id"]
                json_response = JSONResponse({
                    "cached": True,
                    "cached_at": cached.get("cached_at"),
                    "data": cached.get("data"),
                    "refreshed": False,
                    "note": "Webhook unavailable, returning cached data"
                })
                return await add_cors_headers(json_response)
            else:
                json_response = JSONResponse(
                    {"error": "Webhook unavailable and no cached data available"},
                    status_code=503
                )
                return await add_cors_headers(json_response)
        
        # Handle different response formats
        api_data = None
        if isinstance(result, list) and len(result) > 0:
            api_data = result[0]
        elif isinstance(result, dict):
            api_data = result
        else:
            api_data = {"data": result}
        
        # Store in MongoDB (replace any existing cache - keep only latest)
        cache_doc = {
            "cached_at": _now_iso(),
            "data": api_data,
            "source": "webhook"
        }
        
        # Delete old cache entries (keep collection clean)
        await cache_col.delete_many({})
        
        # Insert new cache
        await cache_col.insert_one(cache_doc)
        
        logger.info(f"Stress map data refreshed and cached at {cache_doc['cached_at']}")
        
        json_response = JSONResponse({
            "cached": True,
            "cached_at": cache_doc["cached_at"],
            "data": api_data,
            "refreshed": True
        })
        return await add_cors_headers(json_response)
        
    except Exception as e:
        logger.error(f"Unexpected error refreshing stress map data: {e}", exc_info=True)
        json_response = JSONResponse(
            {"error": f"Failed to refresh stress map data: {str(e)}"},
            status_code=500
        )
        return await add_cors_headers(json_response)