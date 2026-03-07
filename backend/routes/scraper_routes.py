from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional
from loguru import logger

from models.instagram_models import ScrapeRequest
from services.scraper_service import ScraperService
from utils.helpers import validate_usernames

router = APIRouter(prefix="/api/scraper", tags=["scraper"])
scraper_service = ScraperService()

@router.post("/scrape")
async def scrape_instagram_users(request: ScrapeRequest):
    """Scrape Instagram users and optionally their posts"""
    try:
        # Validate usernames
        valid_usernames = validate_usernames(request.usernames)
        if not valid_usernames:
            raise HTTPException(status_code=400, detail="No valid usernames provided")
        
        logger.info(f"Starting scrape for users: {valid_usernames}")
        
        # Perform scraping
        results = await scraper_service.scrape_multiple_users(
            usernames=valid_usernames,
            scrape_posts=request.scrape_posts,
            max_posts_per_user=request.max_posts_per_user
        )
        
        return {
            "success": True,
            "message": f"Scraped {len(results['users'])} users and {len(results['posts'])} posts",
            "data": results
        }
        
    except Exception as e:
        logger.error(f"Scrape failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/scrape/user/{username}")
async def scrape_single_user(username: str, scrape_posts: bool = True, max_pages: Optional[int] = None):
    """Scrape a single Instagram user"""
    try:
        username = username.lstrip('@')
        
        results = {
            "user": await scraper_service.scrape_user_profile(username),
            "posts": []
        }
        
        if scrape_posts:
            results["posts"] = await scraper_service.scrape_user_posts(username, max_pages=max_pages)
        
        return {
            "success": True,
            "data": results
        }
        
    except Exception as e:
        logger.error(f"Failed to scrape user {username}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/scrape/post")
async def scrape_post(url_or_shortcode: str):
    """Scrape a single Instagram post"""
    try:
        post_data = await scraper_service.scrape_post(url_or_shortcode)
        return {
            "success": True,
            "data": post_data
        }
    except Exception as e:
        logger.error(f"Failed to scrape post: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users")
async def get_all_users():
    """Get all users from database"""
    try:
        users = await scraper_service.get_all_users_from_db()
        return {
            "success": True,
            "count": len(users),
            "data": users
        }
    except Exception as e:
        logger.error(f"Failed to get users: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user/{username}")
async def get_user(username: str):
    """Get user data from database"""
    try:
        user = await scraper_service.get_user_from_db(username)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {
            "success": True,
            "data": user
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user {username}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/post/{shortcode}")
async def get_post(shortcode: str):
    """Get post data from database"""
    try:
        post = await scraper_service.get_post_from_db(shortcode)
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        return {
            "success": True,
            "data": post
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get post {shortcode}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """Get status of a scrape job"""
    try:
        job = await scraper_service.get_scrape_job_status(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return {
            "success": True,
            "data": job
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@router.post("/user/{username}/bio-links")
async def scrape_user_bio_links(username: str):
    """Scrape and store bio links for a user"""
    try:
        username = username.lstrip('@')
        result = await scraper_service.scrape_and_store_bio_links(username)
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        logger.error(f"Failed to scrape bio links for {username}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user/{username}/bio-links")
async def get_user_bio_links(username: str):
    """Get bio links for a user"""
    try:
        username = username.lstrip('@')
        bio_links = await scraper_service.get_user_bio_links(username)
        return {
            "success": True,
            "count": len(bio_links),
            "data": bio_links
        }
    except Exception as e:
        logger.error(f"Failed to get bio links for {username}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user/{username}/social-cloud")
async def get_user_social_cloud(username: str):
    """Get social cloud (other social media profiles) for a user"""
    try:
        username = username.lstrip('@')
        social_links = await scraper_service.get_user_social_cloud(username)
        return {
            "success": True,
            "count": len(social_links),
            "data": social_links
        }
    except Exception as e:
        logger.error(f"Failed to get social cloud for {username}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/comments/extract")
async def extract_comment_users():
    """Extract and store comment users from all posts in database"""
    try:
        result = await scraper_service.process_all_comments_from_db()
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        logger.error(f"Failed to extract comment users: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/comments/users/{username}")
async def get_comment_user(username: str):
    """Get comment user data"""
    try:
        from services.comment_service import CommentUserService
        comment_service = CommentUserService()
        
        username = username.lstrip('@')
        user = await comment_service.get_comment_user_from_db(username)
        if not user:
            raise HTTPException(status_code=404, detail="Comment user not found")
        return {
            "success": True,
            "data": user
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get comment user {username}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/comments/users")
async def get_all_comment_users(limit: Optional[int] = None):
    """Get all comment users"""
    try:
        from services.comment_service import CommentUserService
        comment_service = CommentUserService()
        
        users = await comment_service.get_all_comment_users_from_db(limit=limit)
        return {
            "success": True,
            "count": len(users),
            "data": users
        }
    except Exception as e:
        logger.error(f"Failed to get comment users: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/comments/top-commenters")
async def get_top_commenters(limit: int = 10):
    """Get top commenters by total comments"""
    try:
        from services.comment_service import CommentUserService
        comment_service = CommentUserService()
        
        users = await comment_service.get_top_commenters(limit=limit)
        return {
            "success": True,
            "count": len(users),
            "data": users
        }
    except Exception as e:
        logger.error(f"Failed to get top commenters: {e}")
        raise HTTPException(status_code=500, detail=str(e))
