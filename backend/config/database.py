import os
from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

class MongoDB:
    client: AsyncIOMotorClient = None
    db = None  # Primary database (dellinnovate - for analytics/operational data)
    source_db = None  # Source database (instagram_scraper - for posts/users)
    
    @classmethod
    async def connect_db(cls):
        """Connect to MongoDB with dual-database support"""
        try:
            mongodb_uri = os.getenv("MONGODB_URI")
            if not mongodb_uri:
                raise ValueError("MONGODB_URI not found in environment variables")
            
            cls.client = AsyncIOMotorClient(mongodb_uri)
            
            # Primary database for analytics/operational data
            db_name = os.getenv("MONGODB_DB_NAME", "dellinnovate")
            cls.db = cls.client[db_name]
            
            # Source database for Instagram posts/users
            source_db_name = os.getenv("MONGODB_SOURCE_DB_NAME", "instagram_scraper")
            cls.source_db = cls.client[source_db_name]
            
            # Test connection
            await cls.client.admin.command('ping')
            logger.success(f"Connected to MongoDB")
            logger.info(f"  Primary DB (analytics): {db_name}")
            logger.info(f"  Source DB (Instagram): {source_db_name}")
            
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
        """Get primary database instance (dellinnovate - for analytics/operational data)"""
        return cls.db
    
    @classmethod
    def get_source_db(cls):
        """Get source database instance (instagram_scraper - for posts/users)"""
        return cls.source_db
    
    @classmethod
    def get_collection(cls, collection_name):
        """Get a collection from PRIMARY database (dellinnovate)"""
        if cls.db is None:
            raise Exception("Database not connected. Call connect_db first.")
        return cls.db[collection_name]
    
    @classmethod
    def get_source_collection(cls, collection_name):
        """Get a collection from SOURCE database (instagram_scraper)"""
        if cls.source_db is None:
            raise Exception("Database not connected. Call connect_db first.")
        return cls.source_db[collection_name]

# Collections
async def get_users_collection():
    """Get Instagram users collection from SOURCE database"""
    return MongoDB.get_source_collection(os.getenv("MONGODB_COLLECTION_USERS", "instagram_users"))

async def get_posts_collection():
    """Get Instagram posts collection from SOURCE database"""
    return MongoDB.get_source_collection(os.getenv("MONGODB_COLLECTION_POSTS", "instagram_posts"))

async def get_scrapes_collection():
    """Get scrape jobs collection from SOURCE database"""
    return MongoDB.get_source_collection(os.getenv("MONGODB_COLLECTION_SCRAPES", "scrape_jobs"))