#!/usr/bin/env python3
"""
Script to run LLM analysis on risk profiles
Run this when you want to generate summaries for specific users
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

async def run_llm_on_single_user(username: str):
    """
    Run LLM analysis on a single user (when viewing in dashboard)
    
    Args:
        username: Instagram username to analyze
    """
    
    logger.info("=" * 70)
    logger.info(f"🧠 Generating LLM Analysis for @{username}")
    logger.info("=" * 70)
    
    # Connect to MongoDB
    await MongoDB.connect_db()
    db = MongoDB.get_db()
    
    profiles_collection = db.case_risk_profiles
    
    # Find the profile
    profile = await profiles_collection.find_one({"case_user": username})
    
    if not profile:
        logger.error(f"No profile found for user: {username}")
        await MongoDB.close_db()
        return False
    
    logger.info(f"Found profile for {username}")
    logger.info(f"  - Risk Score: {profile.get('risk_score', 0):.1f}/100")
    logger.info(f"  - Risk Level: {profile.get('risk_level', 'Unknown')}")
    
    # Initialize LLM summarizer
    summarizer = LLMSummarizer(use_llm=True)
    
    try:
        # Generate LLM insights for just this one user
        logger.info(f"Generating AI explanation...")
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
                "explanation": llm_insights['explanation'],  # For backward compatibility
                "ai_explanation": llm_insights['explanation']  # For backward compatibility
            }}
        )
        
        logger.success(f"✓ Successfully generated AI explanation for @{username}")
        logger.info(f"  Category: {llm_insights['llm_category']}")
        logger.info(f"  Recommendations: {len(llm_insights['recommendations'])}")
        
        # Print preview of explanation
        preview = llm_insights['explanation'][:150] + "..." if len(llm_insights['explanation']) > 150 else llm_insights['explanation']
        logger.info(f"  Preview: {preview}")
        
        await MongoDB.close_db()
        return True
        
    except Exception as e:
        logger.error(f"✗ Failed to generate explanation for {username}: {e}")
        await MongoDB.close_db()
        return False

async def run_llm_on_multiple_users(limit: int = 5):
    """
    Run LLM analysis on multiple users (for batch processing)
    
    Args:
        limit: Maximum number of users to process
    """
    
    logger.info("=" * 70)
    logger.info(f"🧠 Running LLM Analysis on up to {limit} Users")
    logger.info("=" * 70)
    
    # Connect to MongoDB
    await MongoDB.connect_db()
    db = MongoDB.get_db()
    
    profiles_collection = db.case_risk_profiles
    
    # Find profiles without LLM analysis
    query = {"has_llm_analysis": {"$ne": True}}
    cursor = profiles_collection.find(query).limit(limit)
    profiles = await cursor.to_list(length=limit)
    
    if not profiles:
        logger.warning("No profiles found without LLM analysis")
        await MongoDB.close_db()
        return
    
    logger.info(f"Found {len(profiles)} profiles to process")
    
    # Initialize LLM summarizer
    summarizer = LLMSummarizer(use_llm=True)
    
    # Process each profile
    updated = 0
    failed = 0
    
    for i, profile in enumerate(profiles, 1):
        case_user = profile.get('case_user', 'Unknown')
        logger.info(f"[{i}/{len(profiles)}] Processing @{case_user}...")
        
        try:
            # Generate LLM insights
            llm_insights = await summarizer.summarize_risk_profile(profile)
            
            # Update profile
            await profiles_collection.update_one(
                {"_id": profile["_id"]},
                {"$set": {
                    "llm_explanation": llm_insights['explanation'],
                    "llm_category": llm_insights['llm_category'],
                    "llm_recommendations": llm_insights['recommendations'],
                    "llm_generated_at": llm_insights['generated_at'],
                    "has_llm_analysis": True,
                    "explanation": llm_insights['explanation'],
                    "ai_explanation": llm_insights['explanation']
                }}
            )
            
            updated += 1
            logger.success(f"✓ Updated @{case_user}")
            
            # Wait a bit between users to avoid rate limits
            if i < len(profiles):
                logger.info("Waiting 5 seconds before next user...")
                await asyncio.sleep(5)
            
        except Exception as e:
            logger.error(f"✗ Failed to process @{case_user}: {e}")
            failed += 1
    
    logger.info("=" * 70)
    logger.success(f"LLM Analysis Complete!")
    logger.info(f"Processed: {len(profiles)}")
    logger.info(f"Updated: {updated}")
    logger.info(f"Failed: {failed}")
    logger.info("=" * 70)
    
    await MongoDB.close_db()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run LLM analysis on risk profiles")
    parser.add_argument("--user", type=str, help="Process only this specific user (use when viewing in dashboard)")
    parser.add_argument("--batch", type=int, help="Process multiple users without LLM analysis")
    
    args = parser.parse_args()
    
    if args.user:
        # Single user mode - use this when someone views a profile
        asyncio.run(run_llm_on_single_user(args.user))
    elif args.batch:
        # Batch mode - for background processing
        asyncio.run(run_llm_on_multiple_users(limit=args.batch))
    else:
        print("Please specify either --user <username> or --batch <limit>")
        print("Examples:")
        print("  python scripts/run_llm_on_profiles.py --user crime101film")
        print("  python scripts/run_llm_on_profiles.py --batch 5")