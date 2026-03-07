"""
SCS MongoDB Setup Script
Creates collections and indexes for case management
"""

import asyncio
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

async def setup_scs_collections():
    """Create SCS collections and indexes"""
    
    # Connect to MongoDB
    mongodb_uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("SCS_DB_NAME", "dellinnovate")
    
    if not mongodb_uri:
        logger.error("MONGODB_URI not found in environment")
        return
    
    client = AsyncIOMotorClient(mongodb_uri)
    db = client[db_name]
    
    logger.info(f"Setting up SCS collections in {db_name}...")
    
    # 1. scs_cases collection
    logger.info("Creating scs_cases collection...")
    await db.create_collection("scs_cases")
    
    # Indexes for scs_cases
    await db.scs_cases.create_index("case_id", unique=True)
    await db.scs_cases.create_index("user_id", unique=True)
    await db.scs_cases.create_index("assigned_to")
    await db.scs_cases.create_index("priority")
    await db.scs_cases.create_index("case_status")
    await db.scs_cases.create_index("work_status")
    await db.scs_cases.create_index("current_risk_score")
    
    # 2. scs_case_history collection
    logger.info("Creating scs_case_history collection...")
    await db.create_collection("scs_case_history")
    
    # Indexes for scs_case_history
    await db.scs_case_history.create_index([("case_id", 1), ("history_id", 1)], unique=True)
    await db.scs_case_history.create_index("case_id")
    await db.scs_case_history.create_index("ingestion_date")
    
    # 3. scs_checklist collection
    logger.info("Creating scs_checklist collection...")
    await db.create_collection("scs_checklist")
    
    # Indexes for scs_checklist
    await db.scs_checklist.create_index([("case_id", 1), ("checklist_item_id", 1)], unique=True)
    await db.scs_checklist.create_index("case_id")
    await db.scs_checklist.create_index("completed")
    await db.scs_checklist.create_index("is_mandatory")
    
    # 4. scs_checklist_templates collection
    logger.info("Creating scs_checklist_templates collection...")
    await db.create_collection("scs_checklist_templates")
    
    # Indexes for scs_checklist_templates
    await db.scs_checklist_templates.create_index("template_id", unique=True)
    await db.scs_checklist_templates.create_index("is_active")
    
    # 5. scs_users collection
    logger.info("Creating scs_users collection...")
    await db.create_collection("scs_users")
    
    # Indexes for scs_users
    await db.scs_users.create_index("user_id", unique=True)
    await db.scs_users.create_index("email", unique=True)
    await db.scs_users.create_index("is_active")
    
    # 6. counters collection (for auto-incrementing IDs)
    logger.info("Creating counters collection...")
    await db.create_collection("counters")
    
    # Initialize counters
    await db.counters.update_one(
        {"_id": "case_id_2026"},
        {"$setOnInsert": {"sequence": 0}},
        upsert=True
    )
    
    logger.success("SCS collections setup complete!")
    
    # Insert sample user
    logger.info("Inserting sample user...")
    sample_user = {
        "user_id": "sarah_l",
        "name": "Sarah Lim",
        "email": "sarah.lim@childrensociety.org.sg",
        "role": "youth_worker",
        "is_active": True,
        "created_at": datetime.utcnow()
    }
    
    try:
        await db.scs_users.update_one(
            {"user_id": "sarah_l"},
            {"$setOnInsert": sample_user},
            upsert=True
        )
        logger.success("Sample user created")
    except Exception as e:
        logger.warning(f"Could not create sample user: {e}")
    
    client.close()
    logger.success("SCS MongoDB setup completed!")

if __name__ == "__main__":
    from datetime import datetime
    asyncio.run(setup_scs_collections())