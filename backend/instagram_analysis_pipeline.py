#!/usr/bin/env python3
import asyncio
import json
import pandas as pd
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import sys
sys.path.append(os.path.dirname(__file__))

from services.nlp_service import NLPService
from services.scraper_service import ScraperService
from services.pattern_analysis_service import get_pattern_service
from config.database import MongoDB
from loguru import logger


class InstagramAnalysisPipeline:
    """Complete end-to-end pipeline for Instagram comment analysis"""
    
    def __init__(self, output_dir: str = "analysis_results"):
        """Initialize the pipeline"""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.nlp_service = None
        self.scraper_service = None
        
        logger.info("🚀 Instagram Analysis Pipeline initialized")
    
    async def initialize_services(self):
        """Initialize all required services"""
        logger.info("🔄 Initializing services...")
        
        # Connect to database
        await MongoDB.connect_db()
        
        # Initialize NLP service (loads ML models)
        logger.info("📚 Loading NLP models and pattern analysis...")
        self.nlp_service = NLPService()
        
        # Initialize pattern analysis service
        self.pattern_service = get_pattern_service()
        
        # Initialize scraper service
        self.scraper_service = ScraperService()
        
        logger.success("✅ All services initialized")
    
    async def analyze_instagram_user(
        self, 
        username: str, 
        max_posts: int = 10,
        scrape_new_data: bool = True
    ) -> Dict:
        """
        Complete analysis of an Instagram user's comments
        
        Args:
            username: Instagram username to analyze
            max_posts: Maximum number of posts to process
            scrape_new_data: Whether to scrape fresh data or use existing
            
        Returns:
            Complete analysis results
        """
        logger.info(f"🎯 Starting complete analysis for @{username}")
        
        # Step 1: Data Collection
        if scrape_new_data:
            logger.info("📥 Step 1: Scraping Instagram data...")
            try:
                # Scrape user profile and posts
                await self.scraper_service.scrape_user_profile(username)
                
                # Get posts with comments
                posts_data = await self.scraper_service.get_user_posts_with_comments(
                    username, limit=max_posts
                )
                
                if not posts_data:
                    logger.warning(f"No posts found for @{username}")
                    return {"error": "No posts found"}
                
                logger.success(f"📊 Scraped {len(posts_data)} posts")
                
            except Exception as e:
                logger.error(f"Error scraping data: {e}")
                return {"error": f"Scraping failed: {e}"}
        else:
            logger.info("📂 Step 1: Loading existing data...")
            posts_data = await self.scraper_service.get_user_posts_with_comments(
                username, limit=max_posts
            )
            
            if not posts_data:
                logger.warning(f"No existing data found for @{username}")
                return {"error": "No existing data found"}
        
        # Step 2: Extract and analyze all comments
        logger.info("🧠 Step 2: Analyzing comments with NLP...")
        all_comments = []
        
        for post in posts_data:
            if 'comments' in post and post['comments']:
                for comment in post['comments']:
                    comment_data = {
                        'user': comment.get('owner', 'unknown'),
                        'text': comment.get('text', ''),
                        'post_shortcode': post.get('shortcode', ''),
                        'post_owner': username,
                        'comment_id': comment.get('id', ''),
                        'likes': comment.get('likes', 0),
                        'created_at': comment.get('created_at', '')
                    }
                    all_comments.append(comment_data)
        
        if not all_comments:
            logger.warning("No comments found to analyze")
            return {"error": "No comments found"}
        
        logger.info(f"💬 Processing {len(all_comments)} comments...")
        
        # Analyze each comment
        analyzed_comments = []
        for i, comment in enumerate(all_comments, 1):
            if comment['text'].strip():  # Only analyze non-empty comments
                try:
                    analysis = self.nlp_service.analyze_text(comment['text'])
                    
                    # Combine comment metadata with analysis
                    analyzed_comment = {
                        **comment,
                        **analysis,
                        'analysis_timestamp': datetime.now().isoformat()
                    }
                    
                    analyzed_comments.append(analyzed_comment)
                    
                    if i % 10 == 0:
                        logger.info(f"  Processed {i}/{len(all_comments)} comments")
                        
                except Exception as e:
                    logger.error(f"Error analyzing comment {i}: {e}")
                    continue
        
        logger.success(f"🎉 Analyzed {len(analyzed_comments)} comments")
        
        # Step 3: Generate analysis results
        logger.info("📊 Step 3: Generating analysis results...")
        
        # Create analysis DataFrame
        df = self.nlp_service.create_signal_dataframe(analyzed_comments)
        
        # Generate timestamp for files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Step 4: Export results
        logger.info("💾 Step 4: Exporting results...")
        
        # Export detailed CSV
        csv_path = self.output_dir / f"{username}_analysis_{timestamp}.csv"
        df.to_csv(csv_path, index=False, encoding='utf-8')
        
        # Export summary JSON
        summary = self._generate_analysis_summary(df, username, analyzed_comments)
        json_path = self.output_dir / f"{username}_summary_{timestamp}.json"
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        logger.success(f"📄 Results exported:")
        logger.success(f"  📊 Detailed CSV: {csv_path}")
        logger.success(f"  📋 Summary JSON: {json_path}")
        
        return {
            "username": username,
            "total_comments": len(analyzed_comments),
            "analysis_summary": summary,
            "csv_path": str(csv_path),
            "json_path": str(json_path)
        }
    
    async def analyze_from_existing_data(
        self, 
        data_source: str,
        output_prefix: str = "instagram_analysis"
    ) -> Dict:
        """
        Analyze comments from existing JSON data files
        
        Args:
            data_source: Path to JSON file or directory
            output_prefix: Prefix for output files
            
        Returns:
            Analysis results
        """
        logger.info(f"📂 Analyzing existing data from: {data_source}")
        
        # Load data
        if os.path.isfile(data_source):
            with open(data_source, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            logger.error(f"Data source not found: {data_source}")
            return {"error": "Data source not found"}
        
        # Extract comments based on data structure
        comments = self._extract_comments_from_data(data)
        
        if not comments:
            logger.warning("No comments found in data")
            return {"error": "No comments found"}
        
        logger.info(f"💬 Found {len(comments)} comments to analyze")
        
        # Analyze comments
        analyzed_comments = []
        for comment in comments:
            if comment.get('text', '').strip():
                try:
                    analysis = self.nlp_service.analyze_text(comment['text'])
                    analyzed_comment = {**comment, **analysis}
                    analyzed_comments.append(analyzed_comment)
                except Exception as e:
                    logger.error(f"Error analyzing comment: {e}")
                    continue
        
        # Generate results
        df = self.nlp_service.create_signal_dataframe(analyzed_comments)
        
        # Export
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = self.output_dir / f"{output_prefix}_{timestamp}.csv"
        df.to_csv(csv_path, index=False, encoding='utf-8')
        
        summary = self._generate_analysis_summary(df, "existing_data", analyzed_comments)
        
        logger.success(f"📊 Analysis complete: {csv_path}")
        
        return {
            "source": data_source,
            "total_comments": len(analyzed_comments),
            "analysis_summary": summary,
            "csv_path": str(csv_path)
        }
    
    def _extract_comments_from_data(self, data) -> List[Dict]:
        """Extract comments from various data structures"""
        comments = []
        
        if isinstance(data, dict):
            # Single post
            if 'comments' in data:
                for comment in data['comments']:
                    comments.append({
                        'user': comment.get('owner', 'unknown'),
                        'text': comment.get('text', ''),
                        'post_shortcode': data.get('shortcode', ''),
                        'comment_id': comment.get('id', ''),
                        'likes': comment.get('likes', 0),
                        'created_at': comment.get('created_at', '')
                    })
        
        elif isinstance(data, list):
            # Multiple posts
            for post in data:
                if 'comments' in post and post['comments']:
                    for comment in post['comments']:
                        comments.append({
                            'user': comment.get('owner', 'unknown'),
                            'text': comment.get('text', ''),
                            'post_shortcode': post.get('shortcode', ''),
                            'comment_id': comment.get('id', ''),
                            'likes': comment.get('likes', 0),
                            'created_at': comment.get('created_at', '')
                        })
        
        return comments
    
    def _generate_analysis_summary(self, df: pd.DataFrame, username: str, raw_comments: List[Dict]) -> Dict:
        """Generate comprehensive analysis summary"""
        if len(df) == 0:
            return {"error": "No data to analyze"}
        
        # Basic stats
        total_comments = len(df)
        
        # Distortion analysis
        high_distortion = len(df[df['Distortion_Indicator'] == True])
        distortion_rate = (high_distortion / total_comments) * 100
        
        # Emotion breakdown
        emotions = df['Emotion_Label'].value_counts().to_dict()
        
        # Sentiment breakdown  
        sentiment_counts = df['Sentiment'].value_counts().to_dict()
        avg_sentiment_score = df['Sentiment_Score'].mean()
        
        # Risk indicators (based on negative emotions + sentiment)
        risk_indicators = []
        
        # High sadness
        sadness_count = len(df[df['Sadness_Score'] > 0.5])
        if sadness_count > 0:
            risk_indicators.append(f"{sadness_count} comments with high sadness indicators")
        
        # High anger
        anger_count = len(df[df['Anger_Score'] > 0.5])
        if anger_count > 0:
            risk_indicators.append(f"{anger_count} comments with high anger indicators")
        
        # High fear
        fear_count = len(df[df['Fear_Score'] > 0.5])
        if fear_count > 0:
            risk_indicators.append(f"{fear_count} comments with high fear indicators")
        
        # Very negative sentiment
        very_negative = len(df[df['Sentiment_Score'] < -0.5])
        if very_negative > 0:
            risk_indicators.append(f"{very_negative} comments with very negative sentiment")
        
        # Top concerning comments
        top_concerning = df.nlargest(5, 'Distortion_Score')[
            ['User', 'Comment_Text', 'Emotion_Label', 'Sentiment', 'Distortion_Score']
        ].to_dict('records')
        
        return {
            "analysis_metadata": {
                "username": username,
                "total_comments_analyzed": total_comments,
                "analysis_timestamp": datetime.now().isoformat(),
                "model_info": {
                    "sentiment_model": "cardiffnlp/twitter-xlm-roberta-base-sentiment (Multilingual)",
                    "emotion_model": "cardiffnlp/twitter-roberta-base-emotion-multilabel-latest (English)"
                }
            },
            "emotional_profile": {
                "emotion_distribution": emotions,
                "sentiment_distribution": sentiment_counts,
                "average_sentiment_score": round(avg_sentiment_score, 3),
                "distortion_rate": round(distortion_rate, 2)
            },
            "risk_assessment": {
                "high_distortion_comments": high_distortion,
                "distortion_percentage": round(distortion_rate, 2),
                "risk_indicators": risk_indicators,
                "risk_level": "HIGH" if distortion_rate > 30 else "MODERATE" if distortion_rate > 15 else "LOW"
            },
            "top_concerning_comments": top_concerning,
            "language_analysis": {
                "note": "Sentiment analysis supports multiple languages. Emotion analysis is English-only.",
                "multilingual_support": True
            }
        }
    
    async def cleanup(self):
        """Clean up resources"""
        if MongoDB._client:
            await MongoDB.close_db()


# Demo functions

async def demo_user_analysis():
    """Demo: Analyze a specific Instagram user"""
    pipeline = InstagramAnalysisPipeline()
    
    try:
        await pipeline.initialize_services()
        
        # Example analysis (replace with actual username)
        username = "example_user"  # Replace with actual username
        
        logger.info(f"🎯 Demo: Analyzing Instagram user @{username}")
        
        result = await pipeline.analyze_instagram_user(
            username=username,
            max_posts=5,
            scrape_new_data=False  # Use existing data first
        )
        
        if "error" not in result:
            logger.success("✅ Analysis completed successfully!")
            logger.info(f"📊 Results: {result['analysis_summary']['risk_assessment']['risk_level']} risk level")
        else:
            logger.warning(f"⚠️ Analysis failed: {result['error']}")
    
    except Exception as e:
        logger.error(f"Demo failed: {e}")
    
    finally:
        await pipeline.cleanup()


async def demo_existing_data_analysis():
    """Demo: Analyze existing scraped data"""
    pipeline = InstagramAnalysisPipeline()
    
    try:
        await pipeline.initialize_services()
        
        # Analyze existing sample data
        data_paths = [
            "instagram-scraper/results/multi-image-post.json",
            "instagram-scraper/results/video-post.json"
        ]
        
        for data_path in data_paths:
            if os.path.exists(data_path):
                logger.info(f"📂 Analyzing: {data_path}")
                
                result = await pipeline.analyze_from_existing_data(
                    data_source=data_path,
                    output_prefix=f"demo_{Path(data_path).stem}"
                )
                
                if "error" not in result:
                    logger.success(f"✅ Analyzed {result['total_comments']} comments")
                    
                    # Show summary
                    summary = result['analysis_summary']
                    logger.info(f"🎯 Risk Level: {summary['risk_assessment']['risk_level']}")
                    logger.info(f"📊 Emotions: {list(summary['emotional_profile']['emotion_distribution'].keys())[:3]}")
                else:
                    logger.warning(f"⚠️ Analysis failed: {result['error']}")
            else:
                logger.warning(f"📂 Data file not found: {data_path}")
    
    except Exception as e:
        logger.error(f"Demo failed: {e}")
    
    finally:
        await pipeline.cleanup()


if __name__ == "__main__":
    logger.info("🚀 Instagram Comment Analysis Pipeline")
    logger.info("=" * 60)
    
    # Choose demo to run
    print("\nAvailable demos:")
    print("1. Analyze existing scraped data")
    print("2. Analyze specific Instagram user (requires username)")
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    if choice == "1":
        logger.info("🎬 Running: Existing Data Analysis Demo")
        asyncio.run(demo_existing_data_analysis())
    elif choice == "2":
        username = input("Enter Instagram username: ").strip()
        if username:
            async def custom_user_demo():
                pipeline = InstagramAnalysisPipeline()
                try:
                    await pipeline.initialize_services()
                    result = await pipeline.analyze_instagram_user(username, max_posts=3)
                    logger.info(f"Analysis result: {result}")
                finally:
                    await pipeline.cleanup()
            
            asyncio.run(custom_user_demo())
        else:
            logger.error("No username provided")
    else:
        logger.info("🎬 Running: Default Demo (Existing Data)")
        asyncio.run(demo_existing_data_analysis())