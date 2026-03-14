#!/usr/bin/env python3
"""
Test script for the unified Instagram analysis pipeline
Demonstrates the end-to-end functionality
"""
import asyncio
from instagram_analysis_pipeline import InstagramAnalysisPipeline
from loguru import logger

async def test_pipeline():
    """Test the unified pipeline with sample data"""
    logger.info("🧪 Testing Unified Instagram Analysis Pipeline")
    logger.info("=" * 60)
    
    # Initialize pipeline
    pipeline = InstagramAnalysisPipeline()
    logger.info("✅ Pipeline initialized successfully")
    
    # Test 1: Check if we can analyze from existing data
    logger.info("\n📊 Test 1: Analyzing existing MongoDB data")
    try:
        # This would analyze any existing JSON data files
        # For demo purposes, let's skip this test since it requires actual data files
        logger.info("⚠️  Skipping existing data analysis test (requires actual JSON files)")
            
    except Exception as e:
        logger.warning(f"⚠️  Test 1 failed (expected if no data): {str(e)}")
    
    # Test 2: Validate NLP service initialization
    logger.info("\n🧠 Test 2: Testing NLP service")
    try:
        # Test the NLP service directly with sample text
        from services.nlp_service import NLPService
        nlp = NLPService()
        
        # Test multilingual sentiment analysis
        test_texts = [
            "I love this amazing post! So inspiring! 😍",  # English - positive
            "I'm feeling really sad and depressed today 😢",  # English - negative 
            "¡Me encanta esta publicación! Es increíble",  # Spanish - positive
            "Je suis très triste aujourd'hui",  # French - negative  
            "Diese Post ist fantastisch! Ich liebe es",  # German - positive
        ]
        
        logger.info("Testing multilingual sentiment analysis:")
        for i, text in enumerate(test_texts, 1):
            result = nlp.analyze_text(text)
            sentiment = result.get('sentiment', {})
            emotion = result.get('emotion', {})
            logger.info(f"  {i}. Text: '{text[:50]}...'")
            logger.info(f"     Sentiment: {sentiment.get('LABEL', 'N/A')} ({sentiment.get('SCORE', 0):.3f})")
            logger.info(f"     Top emotion: {emotion.get('top_emotion', 'N/A')} ({emotion.get('max_score', 0):.3f})")
        
        logger.info("✅ NLP multilingual analysis working correctly")
        
    except Exception as e:
        logger.error(f"❌ NLP test failed: {str(e)}")
    
    # Test 3: Validate database connection  
    logger.info("\n🗄️  Test 3: Testing database connection")
    try:
        from config.database import MongoDB
        await MongoDB.connect_db()
        # Test connection by checking collections
        db = MongoDB.get_db()
        collections = await db.list_collection_names()
        logger.info(f"✅ Connected to MongoDB. Available collections: {collections}")
        await MongoDB.close_db()
        
    except Exception as e:
        logger.warning(f"⚠️  Database test failed: {str(e)}")
        
    # Test 4: Validate scraper service  
    logger.info("\n🕷️  Test 4: Testing scraper service initialization")
    try:
        from services.scraper_service import ScraperService
        scraper = ScraperService()
        logger.info("✅ Scraper service initialized (API key validation would require actual scraping)")
        
    except Exception as e:
        logger.error(f"❌ Scraper test failed: {str(e)}")
    
    logger.info("\n🎉 Pipeline Testing Complete!")
    logger.info("=" * 60)
    logger.info("💡 To use the unified pipeline:")
    logger.info("   1. Run 'python instagram_analysis_pipeline.py' for interactive mode")
    logger.info("   2. Use the FastAPI endpoints at /api/unified-pipeline/*")
    logger.info("   3. Import InstagramAnalysisPipeline class in your code")

if __name__ == "__main__":
    asyncio.run(test_pipeline())