"""
Automated Pipeline Scheduler

Schedules the full NLP → Risk Scoring → Case Promotion pipeline to run every 6 hours.
Handles errors, logging, and retries.
"""

import asyncio
import schedule
import time
from datetime import datetime
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from analytics.signal_extraction import run_nlp_extraction
from analytics.stage2_pca_llm import run_case_scoring
from services.case_promotion import promote_risk_profiles_to_scs_cases
from config.database import MongoDB

load_dotenv()

# Configuration
SCHEDULE_INTERVAL_HOURS = 6
USE_LLM = os.getenv("USE_LLM_CALIBRATION", "true").lower() == "true"
WINDOW_DAYS = int(os.getenv("ANALYTICS_WINDOW_DAYS", "30"))
MIN_PRIORITY = os.getenv("MIN_CASE_PRIORITY", "medium")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")


async def run_full_pipeline():
    """
    Execute the complete pipeline:
    1. NLP signal extraction
    2. PCA + LLM risk scoring
    3. Case promotion to SCS tables
    """
    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    logger.info("="*80)
    logger.info(f"Starting Automated Pipeline Run - {run_id}")
    logger.info("="*80)
    
    start_time = datetime.utcnow()
    
    try:
        # Connect to database
        await MongoDB.connect_db()
        db = MongoDB.get_db()
        
        # Stage 1: NLP Signal Extraction
        logger.info("\n[Stage 1] Extracting NLP signals from Instagram data...")
        stage1_start = time.time()
        
        stage1_results = await run_nlp_extraction(
            case_users=None,  # Process all users
            limit=None
        )
        
        stage1_duration = time.time() - stage1_start
        logger.info(f"✓ Stage 1 complete in {stage1_duration:.1f}s")
        logger.info(f"  Text units processed: {stage1_results.get('text_units_processed', 0)}")
        logger.info(f"  Users analyzed: {stage1_results.get('users_count', 0)}")
        
        # Stage 2: PCA + LLM Risk Scoring
        logger.info("\n[Stage 2] Computing risk profiles with PCA + LLM...")
        stage2_start = time.time()
        
        stage2_results = await run_case_scoring(
            db=db,
            window_days=WINDOW_DAYS,
            limit_users=None,
            use_llm=USE_LLM,
            llm_model="llama2",
            ollama_url=OLLAMA_URL
        )
        
        stage2_duration = time.time() - stage2_start
        logger.info(f"✓ Stage 2 complete in {stage2_duration:.1f}s")
        logger.info(f"  Profiles computed: {stage2_results.get('n_profiles', 0)}")
        
        # Stage 3: Promote to SCS Cases
        logger.info("\n[Stage 3] Promoting risk profiles to operational SCS tables...")
        stage3_start = time.time()
        
        stage3_results = await promote_risk_profiles_to_scs_cases(
            db=db,
            min_priority=MIN_PRIORITY,
            limit=None,
            ingestion_timestamp=start_time
        )
        
        stage3_duration = time.time() - stage3_start
        logger.info(f"✓ Stage 3 complete in {stage3_duration:.1f}s")
        logger.info(f"  Cases created: {stage3_results['cases_created']}")
        logger.info(f"  Cases updated: {stage3_results['cases_updated']}")
        logger.info(f"  History entries: {stage3_results['history_entries_added']}")
        logger.info(f"  Checklist items: {stage3_results['checklist_items_created']}")
        
        if stage3_results['errors']:
            logger.warning(f"  ⚠️  Errors encountered: {len(stage3_results['errors'])}")
            for error in stage3_results['errors'][:5]:  # Log first 5 errors
                logger.warning(f"    - {error}")
        
        # Summary
        total_duration = (datetime.utcnow() - start_time).total_seconds()
        logger.info("\n" + "="*80)
        logger.info(f"✓ Pipeline Run {run_id} Complete!")
        logger.info(f"  Total Duration: {total_duration:.1f}s")
        logger.info(f"  Stage 1: {stage1_duration:.1f}s")
        logger.info(f"  Stage 2: {stage2_duration:.1f}s")
        logger.info(f"  Stage 3: {stage3_duration:.1f}s")
        logger.info("="*80)
        
        # Log to pipeline history (optional)
        await log_pipeline_run(db, run_id, {
            "start_time": start_time,
            "duration_seconds": total_duration,
            "stage1_results": stage1_results,
            "stage2_results": stage2_results,
            "stage3_results": stage3_results,
            "status": "success"
        })
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        
        # Log failure
        try:
            await log_pipeline_run(db, run_id, {
                "start_time": start_time,
                "duration_seconds": (datetime.utcnow() - start_time).total_seconds(),
                "error": str(e),
                "status": "failed"
            })
        except:
            pass
        
        return False
    
    finally:
        await MongoDB.close_db()


async def log_pipeline_run(db, run_id: str, results: dict):
    """Log pipeline execution to database for monitoring"""
    try:
        log_entry = {
            "run_id": run_id,
            "timestamp": datetime.utcnow(),
            **results
        }
        
        await db.pipeline_execution_log.insert_one(log_entry)
        logger.debug(f"Logged pipeline run {run_id} to database")
    except Exception as e:
        logger.warning(f"Failed to log pipeline run: {e}")


def run_pipeline_sync():
    """Synchronous wrapper for scheduler"""
    logger.info("\n🕐 Scheduled pipeline execution triggered")
    success = asyncio.run(run_full_pipeline())
    
    if success:
        logger.info(f"✓ Next run in {SCHEDULE_INTERVAL_HOURS} hours\n")
    else:
        logger.error(f"✗ Pipeline failed. Next retry in {SCHEDULE_INTERVAL_HOURS} hours\n")


def main():
    """Main scheduler loop"""
    logger.info("="*80)
    logger.info("🚀 NLP Analytics Pipeline Scheduler")
    logger.info("="*80)
    logger.info(f"\nConfiguration:")
    logger.info(f"  Interval: Every {SCHEDULE_INTERVAL_HOURS} hours")
    logger.info(f"  Window: {WINDOW_DAYS} days")
    logger.info(f"  LLM Calibration: {USE_LLM}")
    logger.info(f"  Min Priority: {MIN_PRIORITY}")
    logger.info(f"  Ollama URL: {OLLAMA_URL}")
    logger.info("\n" + "="*80)
    
    # Set up schedule
    schedule.every(SCHEDULE_INTERVAL_HOURS).hours.do(run_pipeline_sync)
    
    # Run immediately on startup
    logger.info("\n🚀 Running initial pipeline execution...")
    run_pipeline_sync()
    
    # Run on schedule
    logger.info(f"\n⏰ Scheduler active. Pipeline will run every {SCHEDULE_INTERVAL_HOURS} hours.")
    logger.info("   Press Ctrl+C to stop.\n")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logger.info("\n\n🛑 Scheduler stopped by user")


if __name__ == "__main__":
    # Configure logging
    logger.remove()  # Remove default handler
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    logger.add(
        "logs/pipeline_scheduler.log",
        rotation="1 day",
        retention="30 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        level="INFO"
    )
    
    logger.info("Starting scheduler...")
    main()
