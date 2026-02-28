"""
Unified Instagram Comment Analysis CSV Generator
Combines NLP sentiment/emotion analysis with advanced pattern analysis
"""
import asyncio
import os
import json
import pandas as pd
from datetime import datetime
from typing import List, Dict
from loguru import logger

from config.database import MongoDB
from services.nlp_service import NLPService
from services.pattern_analysis_service import PatternAnalysisService

async def generate_unified_csv():
    """Generate unified CSV with complete NLP and pattern analysis"""
    logger.info("🚀 Starting Unified Instagram Comment Analysis")
    logger.info("=" * 60)
    
    try:
        # Connect to database
        await MongoDB.connect_db()
        logger.info("✅ Connected to MongoDB")
        
        # Initialize NLP service and pattern analysis separately
        nlp = NLPService()
        pattern_service = PatternAnalysisService()
        logger.info("✅ NLP service and pattern analysis initialized")
        
        # Create output directory
        output_dir = "analysis_output"
        os.makedirs(output_dir, exist_ok=True)
        
        # For demonstration, analyze sample comments with real NLP service
        logger.info("📝 Analyzing sample comments with unified NLP + Pattern Analysis...")
        
        sample_texts = [
            "I love this post! So inspiring and amazing! 😍 Really made my day better!",
            "I'm feeling really sad and hopeless today 😢 Nothing seems to go right anymore",
            "I always mess everything up. I'm such a complete failure at everything I try. Nothing ever goes right for me.",
            "Thanks for sharing this helpful content! Really appreciate it 😊",
            "Why does everyone hate me? I must be a terrible person. I should just give up on everything.",
            "This is awesome! Best day ever! Can't wait to try this myself!",
            "I can't handle this anymore. Everything is falling apart. What if I never get better? I'm so scared.",
            "Great post! Love the positive energy. Keep up the amazing work! 💪"
        ]
        
        # Analyze each comment with the unified NLP service
        analyzed_comments = []
        for i, text in enumerate(sample_texts):
            logger.info(f"Analyzing comment {i+1}/{len(sample_texts)}")
            
            # Get NLP analysis (Cardiff NLP models) - now working properly
            nlp_result = nlp.analyze_text(text)
            
            # Get pattern analysis separately
            pattern_result = pattern_service.detect_cognitive_distortions(text)
            
            # Combine results
            result = {
                'text': text,
                'comment_id': f'unified_sample_{i+1:03d}',
                'username': f'sample_user_{(i % 3) + 1}',
                'post_id': f'post_{(i % 2) + 1}',
                'timestamp': f"2026-02-28T{8 + i:02d}:30:00Z",
                'likes': max(0, 5 - abs(nlp_result.get('sentiment_score', 0.5) - 0.5) * 10),
                'replies': max(0, int(pattern_result.get('distortion_ratio', 0) / 10))
            }
            
            # Add NLP results
            result.update(nlp_result)
            
            # Add pattern analysis results
            result['cognitive_distortions'] = pattern_result
            
            analyzed_comments.append(result)
            
            # Log key findings
            sentiment = result.get('sentiment', 'unknown')
            emotion = result.get('primary_emotion', 'unknown') 
            distortions = result.get('cognitive_distortions', {})
            
            logger.info(f"  → Sentiment: {sentiment} | Emotion: {emotion}")
            if distortions.get('has_distortions'):
                logger.info(f"  → Distortions: {distortions.get('total_distortions', 0)} detected")
            if distortions.get('total_distortions', 0) > 2:
                logger.info(f"  → ⚠️ High distortion count detected")
        
        # Create comprehensive DataFrame for CSV export
        csv_data = []
        for comment in analyzed_comments:
            # Get nested data safely
            emotions = comment.get('emotions', {})
            cognitive = comment.get('cognitive_distortions', {})
            
            row = {
                # Basic Information
                'Comment_ID': comment.get('comment_id'),
                'Username': comment.get('username'), 
                'Post_ID': comment.get('post_id'),
                'Text': comment.get('text'),
                'Timestamp': comment.get('timestamp'),
                'Likes': comment.get('likes', 0),
                'Replies': comment.get('replies', 0),
                
                # Sentiment Analysis
                'Sentiment': comment.get('sentiment'),
                'Sentiment_Score': comment.get('sentiment_score'),
                'Primary_Emotion': comment.get('primary_emotion'),
                'Primary_Emotion_Score': comment.get('primary_emotion_score'),
                
                # Emotion Scores
                'Joy_Score': emotions.get('joy', 0),
                'Sadness_Score': emotions.get('sadness', 0),
                'Anger_Score': emotions.get('anger', 0),
                'Fear_Score': emotions.get('fear', 0),
                'Love_Score': emotions.get('love', 0),
                'Surprise_Score': emotions.get('surprise', 0),
                
                # Distortion Analysis
                'Distortion_Indicator': comment.get('distortion_indicator', False),
                'Distortion_Score': comment.get('distortion_score', 0),
                
                # Cognitive Distortions (from pattern analysis)
                'Total_Cognitive_Distortions': cognitive.get('total_distortions', 0),
                'Distortion_Ratio': cognitive.get('distortion_ratio', 0),
                'Has_Cognitive_Distortions': cognitive.get('has_distortions', False),
                'Primary_Distortion_Type': cognitive.get('primary_distortion', {}).get('type', '') if isinstance(cognitive.get('primary_distortion'), dict) else cognitive.get('primary_distortion', ''),
                'All_or_Nothing_Count': cognitive.get('all_or_nothing_thinking', {}).get('count', 0),
                'Overgeneralization_Count': cognitive.get('overgeneralization', {}).get('count', 0),
                'Catastrophizing_Count': cognitive.get('catastrophizing', {}).get('count', 0),
                'Personalization_Count': cognitive.get('personalization', {}).get('count', 0),
                'Emotional_Reasoning_Count': cognitive.get('emotional_reasoning', {}).get('count', 0),
                'Should_Statements_Count': cognitive.get('should_statements', {}).get('count', 0),
                'Labeling_Count': cognitive.get('labeling', {}).get('count', 0),
                'Mental_Filtering_Count': cognitive.get('mental_filter', {}).get('count', 0),
                
                # Risk Assessment
                'High_Negative_Emotions': (emotions.get('sadness', 0) > 0.7 or emotions.get('fear', 0) > 0.7),
                'Cognitive_Distortions_Present': cognitive.get('has_distortions', False),
                'Overall_Distortion_Ratio': cognitive.get('distortion_ratio', 0)
            }
            csv_data.append(row)
        
        # Create DataFrame
        df = pd.DataFrame(csv_data)
        
        # Generate output files with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f"{output_dir}/unified_instagram_analysis_{timestamp}.csv"
        json_filename = f"{output_dir}/unified_instagram_analysis_{timestamp}.json"
        summary_filename = f"{output_dir}/unified_analysis_summary_{timestamp}.txt"
        
        # Export CSV
        df.to_csv(csv_filename, index=False, encoding='utf-8')
        logger.success(f"📊 Unified CSV exported: {csv_filename}")
        
        # Export JSON with full analysis data
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(analyzed_comments, f, indent=2, ensure_ascii=False, default=str)
        logger.success(f"📄 Detailed JSON exported: {json_filename}")
        
        # Generate summary statistics
        total_comments = len(analyzed_comments)
        negative_sentiment = len([c for c in analyzed_comments if c.get('sentiment') == 'negative'])
        high_distortion = len([c for c in analyzed_comments if c.get('cognitive_distortions', {}).get('has_distortions')])
        high_risk = len([c for c in analyzed_comments if c.get('risk_indicators', {}).get('high_negative_emotions')])
        
        unique_users = len(set([c.get('username') for c in analyzed_comments]))
        avg_distortion_ratio = sum([c.get('cognitive_distortions', {}).get('distortion_ratio', 0) for c in analyzed_comments]) / total_comments
        
        summary_text = f"""📊 Unified Instagram Comment Analysis Summary
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Analysis Method: NLP Service + Pattern Analysis Integration

🔍 Dataset Overview:
   - Total comments analyzed: {total_comments}
   - Unique users: {unique_users}
   - Analysis columns: {len(df.columns)}

🧠 Sentiment & Emotion Analysis:
   - Negative sentiment: {negative_sentiment} ({negative_sentiment/total_comments*100:.1f}%)
   - Primary emotions: {', '.join(set([c.get('primary_emotion', 'unknown') for c in analyzed_comments if c.get('primary_emotion')]))}

🔄 Cognitive Distortion Analysis:
   - Comments with distortions: {high_distortion} ({high_distortion/total_comments*100:.1f}%)
   - Average distortion ratio: {avg_distortion_ratio:.1f}%

⚠️ Risk Assessment:
   - High-risk indicators: {high_risk} ({high_risk/total_comments*100:.1f}%)
   - Comments requiring attention: {high_distortion + high_risk}

📁 Generated Files:
   - Unified CSV: {csv_filename}
   - Detailed JSON: {json_filename}
   - Summary Report: {summary_filename}

🔧 Technical Notes:
   - Used integrated NLP + Pattern Analysis service
   - Real-time cognitive distortion detection
   - Combined sentiment, emotion, and behavioral analysis
   - Ready for dashboard integration
"""
        
        # Save summary
        with open(summary_filename, 'w', encoding='utf-8') as f:
            f.write(summary_text)
        logger.success(f"📝 Summary report saved: {summary_filename}")
        
        print(f"\\n{summary_text}")
        
        logger.info("🎉 Unified Analysis Complete!")
        logger.info(f"📊 CSV Columns: {len(df.columns)} (includes all NLP + Pattern Analysis features)")
        
        return csv_filename, json_filename, summary_filename
        
    except Exception as e:
        logger.error(f"❌ Error in unified analysis: {e}")
        raise
        
    finally:
        try:
            await MongoDB.close_db()
            logger.info("🔐 Database connection closed")
        except:
            pass

async def analyze_real_user_data(username: str):
    """Analyze real user data from MongoDB with unified analysis"""
    logger.info(f"🔍 Analyzing real data for user: @{username}")
    
    try:
        await MongoDB.connect_db()
        nlp = NLPService()
        
        # Analyze user comments with pattern analysis included
        result = await nlp.analyze_user_comments(
            username=username,
            include_pattern_analysis=True
        )
        
        if result.get('total_comments', 0) == 0:
            logger.warning(f"No comments found for user @{username}")
            return None
            
        # Use the unified CSV creation logic 
        # This would convert the real analysis result to CSV
        logger.success(f"Analyzed {result.get('total_comments')} comments for @{username}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing real user data: {e}")
        return None
    finally:
        await MongoDB.close_db()

if __name__ == "__main__":
    asyncio.run(generate_unified_csv())