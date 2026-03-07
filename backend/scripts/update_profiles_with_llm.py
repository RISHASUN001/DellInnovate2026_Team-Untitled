#!/usr/bin/env python3
"""
Script to update existing risk profiles with LLM analysis
Run this once to add LLM insights to all existing profiles
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

from config.database import MongoDB
from analytics.llm_integration import LLMSummarizer

async def update_all_profiles():
    """Update all risk profiles with LLM analysis"""
    
    logger.info("Connecting to MongoDB...")
    await MongoDB.connect_db()
    
    profiles_collection = MongoDB.get_collection("case_risk_profiles")
    summarizer = LLMSummarizer()
    
    # Get all profiles without LLM analysis
    cursor = profiles_collection.find({
        "$or": [
            {"has_llm_analysis": {"$ne": True}},
            {"llm_summary": {"$exists": False}}
        ]
    })
    
    profiles = await cursor.to_list(length=None)
    logger.info(f"Found {len(profiles)} profiles to update")
    
    updated = 0
    for profile in profiles:
        try:
            username = profile.get('case_user', 'Unknown')
            logger.info(f"Processing {username}...")
            
            llm_insights = await summarizer.summarize_risk_profile(profile)
            
            await profiles_collection.update_one(
                {"_id": profile["_id"]},
                {"$set": {
                    "llm_summary": llm_insights['summary'],
                    "llm_category": llm_insights['llm_category'],
                    "llm_recommendations": llm_insights['recommendations'],
                    "llm_generated_at": llm_insights['generated_at'],
                    "has_llm_analysis": True
                }}
            )
            
            updated += 1
            logger.success(f"Updated {username}")
            
        except Exception as e:
            logger.error(f"Error updating profile {profile.get('case_user')}: {e}")
    
    logger.info(f"Update complete. Updated {updated}/{len(profiles)} profiles")
    await MongoDB.close_db()

if __name__ == "__main__":
    asyncio.run(update_all_profiles())