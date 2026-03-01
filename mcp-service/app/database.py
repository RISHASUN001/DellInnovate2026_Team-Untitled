from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from loguru import logger
from .config import settings
from typing import Optional
from datetime import datetime

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


async def get_db() -> AsyncIOMotorDatabase:
    """Get MongoDB database connection"""
    global _client, _db
    if _db is None:
        mongo_uri = settings.mongodb_uri
        if not mongo_uri:
            raise ValueError("MONGODB_URI not configured")
        
        _client = AsyncIOMotorClient(mongo_uri)
        _db = _client[settings.scs_db_name]
        logger.info(f"MongoDB connected to database: {settings.scs_db_name}")
        
        # Ensure indexes for audit and pending plans collections
        await _ensure_indexes()
    
    return _db


async def _ensure_indexes():
    """Create indexes for audit and pending plans collections"""
    if _db is None:
        return
        
    # Create indexes for audit log
    audit_col = _db['mcp_audit_log']
    await audit_col.create_index('case_id')
    await audit_col.create_index('approved_plan_hash')
    await audit_col.create_index('actor_id')
    await audit_col.create_index('created_at')
    
    # Create indexes for pending plans
    plans_col = _db['mcp_pending_plans']
    await plans_col.create_index('plan_hash', unique=True)
    await plans_col.create_index('case_id')
    await plans_col.create_index('created_at')
    
    logger.info("MCP service indexes ensured")


async def close_db():
    """Close MongoDB connection"""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
        logger.info("MongoDB connection closed")


def serialize_doc(doc: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict"""
    if not doc:
        return doc
    
    # Remove MongoDB _id field
    if "_id" in doc:
        del doc["_id"]
    
    # Convert datetime objects to ISO strings
    for key, value in doc.items():
        if isinstance(value, datetime):
            doc[key] = value.isoformat()
    
    return doc


async def get_next_id(collection_name: str, field_name: str) -> int:
    """Auto-increment ID generator using counters collection"""
    db = await get_db()
    counter_col = db['counters']
    
    result = await counter_col.find_one_and_update(
        {'_id': f"{collection_name}_{field_name}"},
        {'$inc': {'seq': 1}},
        upsert=True,
        return_document=True
    )
    return result['seq']
