"""
Service for extracting and managing comment users
"""
from typing import Dict, List, Optional, Set
from datetime import datetime
from loguru import logger

from config.database import get_comment_users_collection, get_posts_collection
from models.instagram_models import CommentUserModel


class CommentUserService:
    """Service for managing comment users and their comments"""
    
    async def extract_comment_users_from_post(self, post_data: Dict) -> List[Dict]:
        """Extract unique comment users from a single post"""
        comments = post_data.get('comments', [])
        shortcode = post_data.get('shortcode', 'unknown')
        
        if not comments:
            return []
        
        comment_users = {}
        
        for comment in comments:
            username = comment.get('owner')
            if not username:
                continue
            
            if username not in comment_users:
                comment_users[username] = {
                    'username': username,
                    'user_id': comment.get('owner_id'),
                    'comments': [],
                    'posts_commented_on': set()
                }
            
            # Add comment details
            comment_users[username]['comments'].append({
                'comment_id': comment.get('id'),
                'text': comment.get('text'),
                'created_at': comment.get('created_at'),
                'post_shortcode': shortcode,
                'likes': comment.get('likes', 0),
                'viewer_has_liked': comment.get('viewer_has_liked', False)
            })
            
            comment_users[username]['posts_commented_on'].add(shortcode)
        
        # Convert sets to lists for JSON serialization
        for user_data in comment_users.values():
            user_data['posts_commented_on'] = list(user_data['posts_commented_on'])
            user_data['total_comments'] = len(user_data['comments'])
        
        return list(comment_users.values())
    
    async def store_comment_users(self, comment_users_data: List[Dict]) -> int:
        """Store or update comment users in the database"""
        if not comment_users_data:
            return 0
        
        collection = await get_comment_users_collection()
        stored_count = 0
        
        for user_data in comment_users_data:
            username = user_data['username']
            
            try:
                # Check if user exists
                existing = await collection.find_one({'username': username})
                
                if existing:
                    # Merge comments and posts_commented_on
                    existing_comments = existing.get('comments', [])
                    new_comments = user_data['comments']
                    
                    # Get unique comment IDs to avoid duplicates
                    existing_comment_ids = {c.get('comment_id') for c in existing_comments if c.get('comment_id')}
                    
                    # Add only new comments
                    for comment in new_comments:
                        if comment.get('comment_id') not in existing_comment_ids:
                            existing_comments.append(comment)
                    
                    # Merge posts_commented_on
                    existing_posts = set(existing.get('posts_commented_on', []))
                    new_posts = set(user_data['posts_commented_on'])
                    all_posts = list(existing_posts | new_posts)
                    
                    # Update the document
                    await collection.update_one(
                        {'username': username},
                        {
                            '$set': {
                                'comments': existing_comments,
                                'total_comments': len(existing_comments),
                                'posts_commented_on': all_posts,
                                'last_seen': datetime.utcnow(),
                                'user_id': user_data.get('user_id') or existing.get('user_id')
                            }
                        }
                    )
                    logger.info(f"Updated comment user: {username}")
                else:
                    # Insert new comment user
                    model = CommentUserModel(**user_data)
                    await collection.insert_one(model.dict(by_alias=True, exclude={'id', '_id'}))
                    logger.info(f"Inserted new comment user: {username}")
                
                stored_count += 1
                
            except Exception as e:
                logger.error(f"Error storing comment user {username}: {e}")
        
        return stored_count
    
    async def extract_and_store_comment_users_from_post(self, post_data: Dict) -> int:
        """Extract comment users from a post and store them"""
        comment_users = await self.extract_comment_users_from_post(post_data)
        return await self.store_comment_users(comment_users)
    
    async def extract_comment_users_from_multiple_posts(self, posts_data: List[Dict]) -> Dict[str, List[Dict]]:
        """Extract unique comment users from multiple posts"""
        all_comment_users = {}
        
        for post_data in posts_data:
            comment_users = await self.extract_comment_users_from_post(post_data)
            
            for user_data in comment_users:
                username = user_data['username']
                
                if username not in all_comment_users:
                    all_comment_users[username] = user_data
                else:
                    # Merge comments and posts
                    existing = all_comment_users[username]
                    existing['comments'].extend(user_data['comments'])
                    existing['posts_commented_on'] = list(
                        set(existing['posts_commented_on']) | set(user_data['posts_commented_on'])
                    )
                    existing['total_comments'] = len(existing['comments'])
        
        return {
            'comment_users': list(all_comment_users.values()),
            'total_unique_users': len(all_comment_users),
            'total_posts_processed': len(posts_data)
        }
    
    async def get_comment_user_from_db(self, username: str) -> Optional[Dict]:
        """Get comment user data from database"""
        collection = await get_comment_users_collection()
        user = await collection.find_one({'username': username})
        if user:
            user['_id'] = str(user['_id'])
        return user
    
    async def get_all_comment_users_from_db(self, limit: Optional[int] = None) -> List[Dict]:
        """Get all comment users from database"""
        collection = await get_comment_users_collection()
        
        cursor = collection.find()
        if limit:
            cursor = cursor.limit(limit)
        
        users = []
        async for user in cursor:
            user['_id'] = str(user['_id'])
            users.append(user)
        
        return users
    
    async def get_top_commenters(self, limit: int = 10) -> List[Dict]:
        """Get top commenters by total comments"""
        collection = await get_comment_users_collection()
        
        cursor = collection.find().sort('total_comments', -1).limit(limit)
        
        users = []
        async for user in cursor:
            user['_id'] = str(user['_id'])
            users.append(user)
        
        return users
    
    async def process_all_posts_for_comments(self) -> Dict:
        """Process all posts in the database to extract comment users"""
        posts_collection = await get_posts_collection()
        
        cursor = posts_collection.find({'comments': {'$exists': True, '$ne': []}})
        
        all_posts = []
        async for post in cursor:
            all_posts.append(post)
        
        logger.info(f"Found {len(all_posts)} posts with comments")
        
        result = await self.extract_comment_users_from_multiple_posts(all_posts)
        stored_count = await self.store_comment_users(result['comment_users'])
        
        return {
            'total_posts_processed': result['total_posts_processed'],
            'total_unique_comment_users': result['total_unique_users'],
            'stored_count': stored_count
        }
