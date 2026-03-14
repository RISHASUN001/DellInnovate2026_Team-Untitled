"""
Instagram Story Routes

Provides endpoint for fetching Instagram story timestamps for case subjects.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from loguru import logger

from ..services.instagram_story_service import get_story_service


router = APIRouter(prefix="/instagram", tags=["instagram"])


class StoryTimestampResponse(BaseModel):
    """Response model for story timestamps"""
    username: str
    posted_at: str
    expires_at: str
    time_left_seconds: int
    time_left_formatted: str
    is_expired: bool


class StoriesResponse(BaseModel):
    """Response model for stories list"""
    username: str
    stories: List[StoryTimestampResponse]
    total_count: int
    active_count: int
    service_configured: bool
    error_message: Optional[str] = None


@router.get("/stories/{username}", response_model=StoriesResponse)
async def get_story_timestamps(
    username: str,
    include_expired: bool = Query(False, description="Include expired stories")
):
    """
    Fetch Instagram story timestamps for a given username.
    
    This endpoint triggers the Apify actor to fetch the user's current stories
    and returns only the timestamp information (posted_at, expires_at, time_left).
    
    No media links or thumbnails are stored or returned.
    
    Args:
        username: Instagram username (without @)
        include_expired: Whether to include stories that have already expired
    
    Returns:
        List of story timestamps with expiry information
    """
    service = get_story_service()
    
    # Check if service is configured
    if not service.is_configured():
        logger.warning("Instagram story service not configured")
        return StoriesResponse(
            username=username,
            stories=[],
            total_count=0,
            active_count=0,
            service_configured=False
        )
    
    try:
        stories = await service.fetch_story_timestamps(username)
        
        # Convert to response format
        story_responses = []
        active_count = 0
        
        for story in stories:
            # Skip expired unless requested
            if story.is_expired() and not include_expired:
                continue
            
            if not story.is_expired():
                active_count += 1
            
            story_responses.append(StoryTimestampResponse(
                username=story.username,
                posted_at=story.posted_at.isoformat(),
                expires_at=story.expires_at.isoformat(),
                time_left_seconds=story.get_time_left_seconds(),
                time_left_formatted=story.get_time_left_formatted(),
                is_expired=story.is_expired()
            ))
        
        return StoriesResponse(
            username=username,
            stories=story_responses,
            total_count=len(stories),
            active_count=active_count,
            service_configured=True
        )
        
    except ValueError as e:
        logger.warning(f"Invalid request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        error_msg = str(e)
        logger.error(f"Service error for {username}: {error_msg}")
        # Return result with error message instead of HTTP error
        return StoriesResponse(
            username=username,
            stories=[],
            total_count=0,
            active_count=0,
            service_configured=True,
            error_message=error_msg
        )
    except Exception as e:
        error_msg = str(e) if str(e) else "Unknown error occurred"
        logger.exception(f"Unexpected error fetching stories for {username}")
        # Return result with error message instead of HTTP error
        return StoriesResponse(
            username=username,
            stories=[],
            total_count=0,
            active_count=0,
            service_configured=True,
            error_message=error_msg
        )


@router.get("/stories/{username}/status")
async def check_stories_status(username: str):
    """
    Quick check if a user has any active (non-expired) stories.
    
    This is a lighter-weight endpoint that just returns counts without full details.
    """
    service = get_story_service()
    
    if not service.is_configured():
        return {
            "username": username,
            "has_active_stories": False,
            "active_count": 0,
            "service_configured": False,
            "message": "Instagram story service not configured"
        }
    
    try:
        stories = await service.fetch_story_timestamps(username)
        active_stories = [s for s in stories if not s.is_expired()]
        
        # If there are active stories, get the soonest to expire
        soonest_expiry = None
        if active_stories:
            soonest = min(active_stories, key=lambda s: s.expires_at)
            soonest_expiry = {
                "expires_at": soonest.expires_at.isoformat(),
                "time_left_formatted": soonest.get_time_left_formatted(),
                "time_left_seconds": soonest.get_time_left_seconds()
            }
        
        return {
            "username": username,
            "has_active_stories": len(active_stories) > 0,
            "active_count": len(active_stories),
            "total_count": len(stories),
            "soonest_expiry": soonest_expiry,
            "service_configured": True
        }
        
    except Exception as e:
        logger.error(f"Error checking stories status: {e}")
        return {
            "username": username,
            "has_active_stories": False,
            "active_count": 0,
            "service_configured": True,
            "error": str(e)
        }
