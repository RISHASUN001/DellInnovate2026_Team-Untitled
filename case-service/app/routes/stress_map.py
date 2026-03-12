"""
Stress Map caching routes for Singapore Stress Heatmap
- GET /stress-map: Returns cached stress map data from MongoDB
- POST /stress-map/refresh: Calls webhook and updates cached data
"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
import httpx
from loguru import logger
from ..database import get_db

router = APIRouter(prefix="/stress-map", tags=["stress-map"])

WEBHOOK_URL = "https://rishikamehta.app.n8n.cloud/webhook/live-stress-map"
COLLECTION_NAME = "stress_map_cache"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("")
async def get_cached_stress_map():
    """
    Get the most recently cached stress map data from MongoDB.
    Returns 404 if no cached data exists.
    """
    db = await get_db()
    cache_col = db[COLLECTION_NAME]
    
    # Get the most recent cache entry
    cached = await cache_col.find_one(
        {},
        sort=[("cached_at", -1)]
    )
    
    if not cached:
        # No cached data - return empty response with flag
        return {
            "cached": False,
            "message": "No cached data available. Click refresh to fetch data.",
            "data": None
        }
    
    # Remove MongoDB _id field
    if "_id" in cached:
        del cached["_id"]
    
    return {
        "cached": True,
        "cached_at": cached.get("cached_at"),
        "data": cached.get("data")
    }


@router.post("/refresh")
async def refresh_stress_map():
    """
    Fetch fresh stress map data from the webhook and cache it in MongoDB.
    Returns the newly fetched data.
    """
    db = await get_db()
    cache_col = db[COLLECTION_NAME]
    
    try:
        # Call the webhook (3 minute timeout as it can take a while)
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.get(WEBHOOK_URL)
            response.raise_for_status()
            result = response.json()
        
        # API returns an array, extract first item
        api_data = result[0] if isinstance(result, list) and len(result) > 0 else result
        
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
        
        return {
            "cached": True,
            "cached_at": cache_doc["cached_at"],
            "data": api_data,
            "refreshed": True
        }
        
    except httpx.TimeoutException:
        logger.error("Timeout while fetching stress map data from webhook")
        raise HTTPException(
            status_code=504,
            detail="Timeout while fetching stress map data"
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error from webhook: {e.response.status_code}")
        raise HTTPException(
            status_code=502,
            detail=f"Webhook returned error: {e.response.status_code}"
        )
    except Exception as e:
        logger.error(f"Error refreshing stress map data: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh stress map data: {str(e)}"
        )
