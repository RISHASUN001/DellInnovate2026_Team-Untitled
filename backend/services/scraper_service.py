import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from scrapers.instagram_scraper import InstagramScraper
from models.instagram_models import InstagramUserModel, InstagramPostModel, ScrapeJobModel
from config.database import get_users_collection, get_posts_collection, get_scrapes_collection

class ScraperService:
    def __init__(self):
        self.scraper = InstagramScraper()
    
    async def scrape_user_profile(self, username: str) -> Dict[str, Any]:
        """Scrape a single user profile and store in MongoDB"""
        try:
            # Scrape user data
            user_data = await self.scraper.scrape_user(username)
            
            # Create model instance
            user_model = InstagramUserModel(**user_data)
            
            # Store in MongoDB
            users_collection = await get_users_collection()
            
            # Check if user exists and update or insert
            existing = await users_collection.find_one({"username": username})
            if existing:
                # Update existing user - IMPORTANT: exclude _id from update
                user_model.last_updated = datetime.utcnow()
                update_data = user_model.dict(by_alias=True, exclude={"_id", "id"})
                await users_collection.update_one(
                    {"username": username},
                    {"$set": update_data}
                )
                logger.info(f"Updated user {username} in database")
            else:
                # Insert new user
                insert_data = user_model.dict(by_alias=True, exclude={"id"})
                result = await users_collection.insert_one(insert_data)
                logger.info(f"Inserted user {username} with id {result.inserted_id}")
            
            return user_model.dict(by_alias=True)
            
        except Exception as e:
            logger.error(f"Failed to scrape user profile for {username}: {e}")
            raise
    
    async def scrape_post(self, url_or_shortcode: str) -> Dict[str, Any]:
        """Scrape a single post and store in MongoDB"""
        try:
            # Scrape post data
            post_data = await self.scraper.scrape_post(url_or_shortcode)
            
            # Create model instance
            post_model = InstagramPostModel(**post_data)
            
            # Store in MongoDB
            posts_collection = await get_posts_collection()
            
            # Check if post exists and update or insert
            existing = await posts_collection.find_one({"shortcode": post_data["shortcode"]})
            if existing:
                # Update existing post - IMPORTANT: exclude _id from update
                update_data = post_model.dict(by_alias=True, exclude={"_id", "id"})
                await posts_collection.update_one(
                    {"shortcode": post_data["shortcode"]},
                    {"$set": update_data}
                )
                logger.info(f"Updated post {post_data['shortcode']} in database")
            else:
                # Insert new post
                insert_data = post_model.dict(by_alias=True, exclude={"id"})
                result = await posts_collection.insert_one(insert_data)
                logger.info(f"Inserted post {post_data['shortcode']} with id {result.inserted_id}")
            
            return post_model.dict(by_alias=True)
            
        except Exception as e:
            logger.error(f"Failed to scrape post {url_or_shortcode}: {e}")
            raise
    
    async def scrape_user_posts(self, username: str, max_posts: Optional[int] = None) -> List[Dict[str, Any]]:
        """Scrape posts for a user and store in MongoDB, with limit on number of posts"""
        posts = []
        post_count = 0
        
        try:
            # Scrape posts with limit on number of posts
            async for post_data in self.scraper.scrape_user_posts(username, max_pages=None):  # We'll control by post count, not pages
                # Check if we've reached the maximum posts limit
                if max_posts and post_count >= max_posts:
                    logger.info(f"Reached maximum posts limit ({max_posts}) for user {username}")
                    break
                
                # Ensure comments field exists and is a list
                if "comments" not in post_data:
                    post_data["comments"] = []
                elif post_data["comments"] is None:
                    post_data["comments"] = []
                
                # Ensure comments_count matches actual comments length
                if post_data.get("comments"):
                    post_data["comments_count"] = len(post_data["comments"])
                
                # Ensure tagged_users exists
                if "tagged_users" not in post_data:
                    post_data["tagged_users"] = []
                
                # Ensure captions exists
                if "captions" not in post_data:
                    post_data["captions"] = []
                
                # Create model instance
                post_model = InstagramPostModel(**post_data)
                
                # Store in MongoDB
                posts_collection = await get_posts_collection()
                
                # Check if post exists
                existing = await posts_collection.find_one({"shortcode": post_data.get("shortcode")})
                if existing:
                    # Update existing post - IMPORTANT: exclude _id from update
                    update_data = post_model.dict(by_alias=True, exclude={"_id", "id"})
                    await posts_collection.update_one(
                        {"shortcode": post_data["shortcode"]},
                        {"$set": update_data}
                    )
                    logger.debug(f"Updated post {post_data['shortcode']}")
                else:
                    # Insert new post
                    insert_data = post_model.dict(by_alias=True, exclude={"id"})
                    await posts_collection.insert_one(insert_data)
                    logger.debug(f"Inserted post {post_data['shortcode']}")
                
                posts.append(post_model.dict(by_alias=True))
                post_count += 1
            
            logger.info(f"Scraped and stored {len(posts)} posts for user {username} (requested max: {max_posts if max_posts else 'unlimited'})")
            return posts
            
        except Exception as e:
            logger.error(f"Failed to scrape posts for {username}: {e}")
            raise
    
    async def scrape_multiple_users(self, usernames: List[str], scrape_posts: bool = True, 
                                   max_posts_per_user: Optional[int] = None) -> Dict[str, Any]:
        """Scrape multiple users and their posts with post limit per user"""
        # Create a scrape job record
        scrapes_collection = await get_scrapes_collection()
        job = ScrapeJobModel(
            job_type="user_batch",
            targets=usernames,
            status="in_progress"
        )
        job_result = await scrapes_collection.insert_one(job.dict(by_alias=True, exclude={"id"}))
        job_id = job_result.inserted_id
        
        results = {
            "job_id": str(job_id),
            "users": [],
            "posts": []
        }
        
        try:
            for username in usernames:
                try:
                    # Scrape user profile
                    user_data = await self.scrape_user_profile(username)
                    results["users"].append(user_data)
                    
                    # Scrape posts if requested, with post limit
                    if scrape_posts:
                        posts = await self.scrape_user_posts(username, max_posts=max_posts_per_user)
                        results["posts"].extend(posts)
                        
                except Exception as e:
                    logger.error(f"Error processing {username}: {e}")
                    results["users"].append({
                        "username": username,
                        "error": str(e)
                    })
            
            # Update job status
            await scrapes_collection.update_one(
                {"_id": job_id},
                {"$set": {
                    "status": "completed",
                    "completed_at": datetime.utcnow(),
                    "results": results
                }}
            )
            
        except Exception as e:
            # Update job with error
            await scrapes_collection.update_one(
                {"_id": job_id},
                {"$set": {
                    "status": "failed",
                    "completed_at": datetime.utcnow(),
                    "error": str(e)
                }}
            )
            raise
        
        return results
    
    async def get_scrape_job_status(self, job_id: str) -> Optional[Dict]:
        """Get the status of a scrape job"""
        from bson import ObjectId
        
        scrapes_collection = await get_scrapes_collection()
        job = await scrapes_collection.find_one({"_id": ObjectId(job_id)})
        
        if job:
            job["_id"] = str(job["_id"])
            return job
        return None
    
    async def get_user_from_db(self, username: str) -> Optional[Dict]:
        """Get user data from database"""
        users_collection = await get_users_collection()
        user = await users_collection.find_one({"username": username})
        if user:
            user["_id"] = str(user["_id"])
        return user
    
    async def get_post_from_db(self, shortcode: str) -> Optional[Dict]:
        """Get post data from database"""
        posts_collection = await get_posts_collection()
        post = await posts_collection.find_one({"shortcode": shortcode})
        if post:
            post["_id"] = str(post["_id"])
        return post
    
    async def get_all_users_from_db(self) -> List[Dict]:
        """Get all users from database"""
        users_collection = await get_users_collection()
        cursor = users_collection.find()
        users = []
        async for user in cursor:
            user["_id"] = str(user["_id"])
            users.append(user)
        return users