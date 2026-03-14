"""
Instagram Story Timestamp Fetcher Service

Uses the RapidAPI Instagram Scraper Stable API to fetch
Instagram story timestamps and calculate expiry times.

Environment variables required:
- RAPIDAPI_KEY: Your RapidAPI key
"""

import os
import httpx
from datetime import datetime, timezone
from typing import List, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class StoryTimestamp:
    """Minimal story data with only timestamps"""
    username: str
    posted_at: datetime
    expires_at: datetime
    
    def to_dict(self):
        return {
            "username": self.username,
            "posted_at": self.posted_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "time_left_seconds": self.get_time_left_seconds(),
            "time_left_formatted": self.get_time_left_formatted(),
            "is_expired": self.is_expired()
        }
    
    def is_expired(self) -> bool:
        """Check if story has expired"""
        return datetime.now(timezone.utc) > self.expires_at
    
    def get_time_left_seconds(self) -> int:
        """Get remaining time in seconds (0 if expired)"""
        diff = self.expires_at - datetime.now(timezone.utc)
        return max(0, int(diff.total_seconds()))
    
    def get_time_left_formatted(self) -> str:
        """Get human-readable time remaining"""
        seconds = self.get_time_left_seconds()
        if seconds <= 0:
            return "Expired"
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        
        if hours > 0:
            return f"{hours}h {minutes}m remaining"
        elif minutes > 0:
            return f"{minutes}m remaining"
        else:
            return f"{seconds}s remaining"


class InstagramStoryService:
    """Service for fetching Instagram story timestamps via RapidAPI"""
    
    RAPIDAPI_HOST = "instagram-scraper-stable-api.p.rapidapi.com"
    RAPIDAPI_BASE_URL = f"https://{RAPIDAPI_HOST}"
    INSTAGRAM_STORY_DURATION_SECONDS = 86400  # 24 hours
    
    def __init__(self):
        self.api_key = os.getenv("RAPIDAPI_KEY")
        
        if not self.api_key:
            logger.warning("RAPIDAPI_KEY not set - Instagram story fetching will be disabled")
    
    def is_configured(self) -> bool:
        """Check if the service is properly configured"""
        return bool(self.api_key)
    
    async def fetch_story_timestamps(self, username: str) -> List[StoryTimestamp]:
        """
        Fetch Instagram story timestamps for a given username.
        
        Args:
            username: Instagram username (without @)
        
        Returns:
            List of StoryTimestamp objects with posted_at and expires_at
        """
        if not self.is_configured():
            raise ValueError("Instagram story service not configured. Set RAPIDAPI_KEY.")
        
        # Clean username (remove @ if present)
        username = username.lstrip("@").strip()
        
        if not username:
            raise ValueError("Username cannot be empty")
        
        logger.info(f"Fetching Instagram stories for user: {username}")
        
        try:
            # First try to get user stories directly
            stories = await self._fetch_user_stories(username)
            
            if stories:
                logger.info(f"Found {len(stories)} stories for user: {username}")
                return stories
            
            # If no stories from direct endpoint, check if stories are published
            has_stories = await self._check_stories_published(username)
            
            if has_stories:
                logger.info(f"User {username} has stories but couldn't fetch details")
                # Return empty list - stories exist but we couldn't get timestamps
                return []
            else:
                logger.info(f"No active stories for user: {username}")
                return []
            
        except httpx.HTTPStatusError as e:
            error_body = e.response.text
            logger.error(f"RapidAPI error: {e.response.status_code} - {error_body}")
            
            if e.response.status_code == 401:
                raise RuntimeError("Invalid RapidAPI key. Please check your RAPIDAPI_KEY environment variable.")
            elif e.response.status_code == 429:
                raise RuntimeError("RapidAPI rate limit exceeded. Please try again later.")
            else:
                raise RuntimeError(f"RapidAPI error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching Instagram stories: {e}")
            raise
    
    async def _fetch_user_stories(self, username: str) -> List[StoryTimestamp]:
        """Fetch user stories from RapidAPI"""
        url = f"{self.RAPIDAPI_BASE_URL}/get_ig_user_stories.php"
        
        headers = {
            "Content-Type": "application/json",
            "x-rapidapi-host": self.RAPIDAPI_HOST,
            "x-rapidapi-key": self.api_key
        }
        
        payload = {
            "username_or_url": username
        }
        
        logger.info(f"Fetching stories from: {url}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            logger.debug(f"Stories response: {data}")
            
            return self._extract_timestamps_from_stories(username, data)
    
    async def _check_stories_published(self, username: str) -> bool:
        """Check if user has active stories published"""
        url = f"{self.RAPIDAPI_BASE_URL}/are_stories_published.php"
        
        headers = {
            "Content-Type": "application/json",
            "x-rapidapi-host": self.RAPIDAPI_HOST,
            "x-rapidapi-key": self.api_key
        }
        
        params = {
            "username_or_url": username
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            logger.debug(f"Stories published check response: {data}")
            
            # Check various possible response formats
            if isinstance(data, dict):
                return data.get("has_stories", False) or data.get("stories_published", False) or data.get("result", False)
            return bool(data)
    
    def _extract_timestamps_from_stories(self, username: str, data: dict) -> List[StoryTimestamp]:
        """Extract timestamps from RapidAPI stories response"""
        stories = []
        
        # Handle different response structures
        items = []
        
        if isinstance(data, dict):
            # Check for stories array in response
            if "stories" in data:
                items = data["stories"]
            elif "items" in data:
                items = data["items"]
            elif "reel" in data:
                # Single reel object with expiring_at and latest_reel_media
                reel = data["reel"]
                if reel and reel.get("latest_reel_media"):
                    items = [reel]
            elif "data" in data:
                items = data["data"] if isinstance(data["data"], list) else [data["data"]]
            else:
                # The response itself might be the items
                items = [data] if data else []
        elif isinstance(data, list):
            items = data
        
        logger.info(f"Processing {len(items)} story items")
        
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            
            # Try to extract timestamps
            # RapidAPI response may have: expiring_at, latest_reel_media, taken_at, etc.
            expiring_at = item.get("expiring_at") or item.get("expiringAt")
            posted_at_ts = (
                item.get("latest_reel_media") or 
                item.get("taken_at") or 
                item.get("takenAt") or 
                item.get("timestamp") or
                item.get("created_at")
            )
            
            logger.debug(f"Item {idx}: expiring_at={expiring_at}, posted_at_ts={posted_at_ts}")
            
            try:
                # If we have expiring_at but no posted_at, calculate posted_at
                if expiring_at and not posted_at_ts:
                    expires_at = datetime.fromtimestamp(expiring_at, tz=timezone.utc)
                    posted_at = datetime.fromtimestamp(
                        expiring_at - self.INSTAGRAM_STORY_DURATION_SECONDS, 
                        tz=timezone.utc
                    )
                elif posted_at_ts:
                    # Handle milliseconds vs seconds
                    if posted_at_ts > 10000000000:
                        posted_at_ts = posted_at_ts / 1000
                    
                    posted_at = datetime.fromtimestamp(posted_at_ts, tz=timezone.utc)
                    
                    if expiring_at:
                        expires_at = datetime.fromtimestamp(expiring_at, tz=timezone.utc)
                    else:
                        # Calculate expiry (24 hours after posting)
                        expires_at = datetime.fromtimestamp(
                            posted_at_ts + self.INSTAGRAM_STORY_DURATION_SECONDS,
                            tz=timezone.utc
                        )
                else:
                    # No timestamp found, skip
                    continue
                
                # Only add non-expired stories or recently expired ones
                stories.append(StoryTimestamp(
                    username=username,
                    posted_at=posted_at,
                    expires_at=expires_at
                ))
                
            except (ValueError, OSError, TypeError) as e:
                logger.warning(f"Failed to parse timestamps: {e}")
                continue
        
        # Sort by posted_at descending (newest first)
        stories.sort(key=lambda s: s.posted_at, reverse=True)
        
        return stories


# Singleton instance
_story_service: Optional[InstagramStoryService] = None


def get_story_service() -> InstagramStoryService:
    """Get or create the Instagram story service singleton"""
    global _story_service
    if _story_service is None:
        _story_service = InstagramStoryService()
    return _story_service
