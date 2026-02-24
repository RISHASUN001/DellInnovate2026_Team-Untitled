"""
Test script to analyze Instagram comments with NLP
"""
import asyncio
from config.database import MongoDB, get_posts_collection
from services.nlp_service import get_nlp_service
from loguru import logger


async def check_data():
    """Check what data exists in MongoDB"""
    await MongoDB.connect_db()
    
    posts_collection = await get_posts_collection()
    
    # Count total posts
    total_posts = await posts_collection.count_documents({})
    logger.info(f"Total posts in database: {total_posts}")
    
    # Count posts with comments
    posts_with_comments = await posts_collection.count_documents({
        'comments': {'$exists': True, '$ne': []}
    })
    logger.info(f"Posts with comments: {posts_with_comments}")
    
    # Get sample post to see structure
    sample_post = await posts_collection.find_one()
    if sample_post:
        logger.info(f"Sample post structure keys: {list(sample_post.keys())}")
        if 'comments' in sample_post:
            logger.info(f"Comments field type: {type(sample_post.get('comments'))}")
            comments = sample_post.get('comments')
            if comments:
                logger.info(f"Number of comments: {len(comments) if isinstance(comments, list) else 'Not a list'}")
                if isinstance(comments, list) and len(comments) > 0:
                    logger.info(f"Sample comment: {comments[0]}")
    
    await MongoDB.close_db()


async def analyze_all_comments():
    """Analyze all comments from posts"""
    await MongoDB.connect_db()
    
    nlp = get_nlp_service()
    
    # Analyze comments
    logger.info("Starting comment analysis...")
    analyzed = await nlp.analyze_comments_from_posts(limit=None)
    
    logger.success(f"Analyzed {len(analyzed)} comments")
    
    if analyzed:
        # Show first result
        logger.info(f"Sample result: {analyzed[0]}")
        
        # Export to CSV
        output_path = "/home/st1/personal/DellInnovate2026_Team-Untitled/backend/exports/signal_data.csv"
        await nlp.export_signal_csv(
            output_path=output_path,
            source="posts"
        )
        logger.success(f"Exported to {output_path}")
    
    await MongoDB.close_db()


if __name__ == "__main__":
    # First check data
    print("\n=== Checking Data ===")
    asyncio.run(check_data())
    
    # Then analyze
    print("\n=== Analyzing Comments ===")
    asyncio.run(analyze_all_comments())
