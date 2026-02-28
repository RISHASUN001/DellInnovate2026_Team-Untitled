"""
Test Script for PCA + LLM Risk Scoring System

Run this script to validate the new PCA-based scoring implementation.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from config.database import MongoDB
from analytics.stage2_pca_llm import run_case_scoring
from loguru import logger


async def test_pca_scoring():
    """
    Test the PCA + LLM scoring system
    """
    logger.info("=" * 60)
    logger.info("Testing PCA + LLM Risk Scoring System")
    logger.info("=" * 60)
    
    # Initialize database
    await MongoDB.connect_db()
    db = MongoDB.get_db()
    
    # Check if signals exist
    signals_count = await db.text_units_signals.count_documents({})
    logger.info(f"Found {signals_count} text unit signals in database")
    
    if signals_count == 0:
        logger.error("No signals found! Run Stage 1 (NLP extraction) first.")
        return
    
    # Test 1: Run PCA scoring without LLM (fast)
    logger.info("\n" + "=" * 60)
    logger.info("TEST 1: PCA Scoring (No LLM)")
    logger.info("=" * 60)
    
    try:
        result = await run_case_scoring(
            db=db,
            window_days=30,
            limit_users=5,  # Test on 5 users
            use_llm=False  # Skip LLM for faster testing
        )
        
        if result['success']:
            logger.info(f"✓ PCA scoring successful!")
            logger.info(f"  Processed: {result['n_profiles']} users")
            logger.info(f"  PCA run ID: {result['pca_run_id']}")
            
            # Show results
            for i, profile in enumerate(result['profiles'][:3]):  # Show first 3
                logger.info(f"\n  User {i+1}: {profile['username']}")
                logger.info(f"    Emotion score: {profile['emotion_score']:.3f}")
                logger.info(f"    Sentiment score: {profile['sentiment_score']:.3f}")
                logger.info(f"    Harm score: {profile['harm_score']:.3f}")
                logger.info(f"    Text units: {profile['n_units']}")
                logger.info(f"    Damping factor: {profile['damp']:.3f}")
                logger.info(f"    Risk (math): {profile['risk_score_math']:.3f}")
                logger.info(f"    Base score: {profile['base_score']:.3f}")
                logger.info(f"    LLM delta: {profile['llm_delta']:+.3f}")
                logger.info(f"    Final score: {profile['final_score']:.3f}")
                logger.info(f"    Priority: {profile['priority_level']}")
                
                # Validate fields
                assert 0.0 <= profile['final_score'] <= 1.0, "Final score out of range!"
                assert profile['priority_level'] in ['low', 'medium', 'high', 'critical']
                assert 'evidence_unit_ids' in profile
                
            logger.info("\n✓ All validations passed!")
        else:
            logger.error(f"✗ PCA scoring failed: {result.get('message')}")
    
    except Exception as e:
        logger.error(f"✗ TEST 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 2: Run with LLM calibration (requires Ollama)
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: PCA Scoring with LLM Calibration")
    logger.info("=" * 60)
    logger.info("NOTE: This requires Ollama to be running on localhost:11434")
    logger.info("      Run 'ollama serve' in another terminal if not already running")
    
    try:
        result = await run_case_scoring(
            db=db,
            window_days=30,
            limit_users=2,  # Test on 2 users only (LLM is slower)
            use_llm=True,
            llm_model="llama2",
            ollama_url="http://localhost:11434"
        )
        
        if result['success']:
            logger.info(f"✓ LLM calibration successful!")
            logger.info(f"  Processed: {result['n_profiles']} users")
            
            # Show LLM deltas
            for i, profile in enumerate(result['profiles']):
                logger.info(f"\n  User {i+1}: {profile['username']}")
                logger.info(f"    Base score: {profile['base_score']:.3f}")
                logger.info(f"    LLM delta1: {profile.get('llm_delta1', 0):+.3f}")
                logger.info(f"    LLM delta2: {profile.get('llm_delta2', 0):+.3f}")
                logger.info(f"    LLM delta (avg): {profile['llm_delta']:+.3f}")
                logger.info(f"    Final score: {profile['final_score']:.3f}")
                
                # Validate LLM delta bounds
                assert -0.10 <= profile['llm_delta'] <= 0.10, "LLM delta out of bounds!"
                
            logger.info("\n✓ LLM calibration validations passed!")
        else:
            logger.error(f"✗ LLM calibration failed: {result.get('message')}")
            logger.warning("  This is expected if Ollama is not running")
    
    except Exception as e:
        logger.error(f"✗ TEST 2 FAILED: {e}")
        logger.warning("  This is expected if Ollama is not running")
        logger.warning("  Install Ollama from https://ollama.ai/ and run 'ollama serve'")
    
    # Test 3: Verify MongoDB storage
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: MongoDB Storage Verification")
    logger.info("=" * 60)
    
    try:
        # Check if profiles were stored
        profile = await db.case_risk_profiles.find_one({}, sort=[('timestamp', -1)])
        
        if profile:
            logger.info("✓ Found risk profile in database")
            
            # Check for new PCA fields
            required_fields = [
                'emotion_score', 'sentiment_score', 'harm_score',
                'n_units', 'damp', 'risk_score_math', 'base_score',
                'llm_delta', 'final_score', 'priority_level', 'pc1_loadings'
            ]
            
            missing_fields = [f for f in required_fields if f not in profile]
            
            if missing_fields:
                logger.error(f"✗ Missing fields: {missing_fields}")
            else:
                logger.info("✓ All PCA fields present in database")
                
                # Show sample profile
                logger.info(f"\n  Sample profile for: {profile['case_user']}")
                logger.info(f"    Final score: {profile['final_score']:.3f}")
                logger.info(f"    Priority: {profile['priority_level']}")
                logger.info(f"    PCA run ID: {profile.get('pca_run_id', 'N/A')}")
                logger.info(f"    Evidence units: {len(profile.get('evidence_unit_ids', []))}")
        else:
            logger.warning("✗ No risk profiles found in database")
    
    except Exception as e:
        logger.error(f"✗ TEST 3 FAILED: {e}")
    
    logger.info("\n" + "=" * 60)
    logger.info("Testing Complete!")
    logger.info("=" * 60)
    
    await MongoDB.close_db()


if __name__ == "__main__":
    asyncio.run(test_pca_scoring())
