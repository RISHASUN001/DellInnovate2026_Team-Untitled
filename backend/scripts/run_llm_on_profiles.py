#!/usr/bin/env python3
"""
Script to run LLM analysis on existing risk profiles
"""

import asyncio
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from loguru import logger

from analytics.llm_integration import LLMSummarizer
from config.database import MongoDB

load_dotenv()

async def run_llm_on_profiles(limit: int = None, specific_user: str = None):
    """
    Run LLM analysis on risk profiles
    
    Args:
        limit: Maximum number of profiles to process
        specific_user: Process only this specific user
    """
    
    logger.info("=" * 70)
    logger.info("🧠 Running LLM Analysis on Risk Profiles")
    logger.info("=" * 70)
    
    # Connect to MongoDB
    await MongoDB.connect_db()
    db = MongoDB.get_db()
    
    profiles_collection = db.case_risk_profiles
    
    # Build query
    query = {}
    if specific_user:
        query["case_user"] = specific_user
    else:
        # Only process profiles without LLM analysis
        query["has_llm_analysis"] = {"$ne": True}
    
    # Get profiles
    cursor = profiles_collection.find(query)
    if limit:
        cursor = cursor.limit(limit)
    
    profiles = await cursor.to_list(length=limit)
    
    if not profiles:
        logger.warning("No profiles found to process")
        await MongoDB.close_db()
        return
    
    logger.info(f"Found {len(profiles)} profiles to process")
    
    # Initialize LLM summarizer
    summarizer = LLMSummarizer()
    
    # Process each profile
    updated = 0
    failed = 0
    
    for i, profile in enumerate(profiles, 1):
        case_user = profile.get('case_user', 'Unknown')
        logger.info(f"[{i}/{len(profiles)}] Processing {case_user}...")
        
        try:
            # Generate LLM insights
            llm_insights = await summarizer.summarize_risk_profile(profile)
            
            # Update profile with LLM insights
            await profiles_collection.update_one(
                {"_id": profile["_id"]},
                {"$set": {
                    "llm_explanation": llm_insights['explanation'],
                    "llm_category": llm_insights['llm_category'],
                    "llm_recommendations": llm_insights['recommendations'],
                    "llm_generated_at": llm_insights['generated_at'],
                    "has_llm_analysis": True,
                    "explanation": llm_insights['explanation'],  # Also set for backward compatibility
                    "ai_explanation": llm_insights['explanation']  # Also set for backward compatibility
                }}
            )
            
            updated += 1
            logger.success(f"✓ Updated {case_user}")
            
        except Exception as e:
            logger.error(f"✗ Failed to process {case_user}: {e}")
            failed += 1
    
    logger.info("=" * 70)
    logger.success(f"LLM Analysis Complete!")
    logger.info(f"Processed: {len(profiles)}")
    logger.info(f"Updated: {updated}")
    logger.info(f"Failed: {failed}")
    logger.info("=" * 70)
    
    await MongoDB.close_db()

async def run_llm_on_single_user(username: str):
    """Run LLM analysis on a single user"""
    await run_llm_on_profiles(specific_user=username)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run LLM analysis on risk profiles")
    parser.add_argument("--limit", type=int, help="Maximum number of profiles to process")
    parser.add_argument("--user", type=str, help="Process only this specific user")
    
    args = parser.parse_args()
    
    if args.user:
        asyncio.run(run_llm_on_single_user(args.user))
    else:
        asyncio.run(run_llm_on_profiles(limit=args.limit))