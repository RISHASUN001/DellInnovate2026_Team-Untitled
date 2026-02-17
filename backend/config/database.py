import os
from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

class MongoDB:
    client: AsyncIOMotorClient = None
    db = None
    
    @classmethod
    async def connect_db(cls):
        """Connect to MongoDB"""
        try:
            mongodb_uri = os.getenv("MONGODB_URI")
            if not mongodb_uri:
                raise ValueError("MONGODB_URI not found in environment variables")
            
            cls.client = AsyncIOMotorClient(mongodb_uri)
            db_name = os.getenv("MONGODB_DB_NAME", "instagram_scraper")
            cls.db = cls.client[db_name]
            
            # Test connection
            await cls.client.admin.command('ping')
            logger.success(f"Connected to MongoDB database: {db_name}")
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    @classmethod
    async def close_db(cls):
        """Close MongoDB connection"""
        if cls.client:
            cls.client.close()
            logger.info("MongoDB connection closed")
    
    @classmethod
    def get_db(cls):
        """Get database instance"""
        return cls.db
    
    @classmethod
    def get_collection(cls, collection_name):
        """Get collection from database"""
        if cls.db is None:
            raise Exception("Database not connected. Call connect_db first.")
        return cls.db[collection_name]

# Collections
async def get_users_collection():
    return MongoDB.get_collection(os.getenv("MONGODB_COLLECTION_USERS", "instagram_users"))

async def get_posts_collection():
    return MongoDB.get_collection(os.getenv("MONGODB_COLLECTION_POSTS", "instagram_posts"))

async def get_scrapes_collection():
    return MongoDB.get_collection(os.getenv("MONGODB_COLLECTION_SCRAPES", "scrape_jobs"))