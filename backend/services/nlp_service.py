"""
NLP Service for Emotional Tone Extraction and Sentiment Analysis
Uses Hugging Face Transformers for emotion and sentiment analysis on social media text
"""
from typing import Dict, List, Optional, Union
from datetime import datetime
import pandas as pd
from loguru import logger
from transformers import pipeline
import torch

from config.database import get_posts_collection, get_comment_users_collection
from services.pattern_analysis_service import get_pattern_service


class NLPService:
    """
    Service for emotion and sentiment analysis using Hugging Face models
    
    Models:
    - Emotion Analysis: English-only (CardiffNLP RoBERTa)
    - Sentiment Analysis: Multilingual (CardiffNLP XLM-RoBERTa)
      Supports: English, Spanish, French, German, Italian, Portuguese, Dutch, and more
    """
    
    def __init__(self):
        """Initialize NLP models"""
        self.emotion_analyzer = None
        self.sentiment_analyzer = None
        self.pattern_service = get_pattern_service()
        self._load_models()
    
    def _load_models(self):
        """Load pre-trained models for emotion and sentiment analysis"""
        try:
            # Check if CUDA is available
            device = 0 if torch.cuda.is_available() else -1
            logger.info(f"Using device: {'GPU' if device == 0 else 'CPU'}")
            
            # Load emotion classification model (CardiffNLP RoBERTa)
            # This model classifies emotions into: sadness, joy, love, anger, fear, surprise
            logger.info("Loading emotion classifier...")
            self.emotion_analyzer = pipeline(
                "text-classification",
                model="cardiffnlp/twitter-roberta-base-emotion-multilabel-latest",
                device=device,
                top_k=None  # Return all emotion scores
            )
            
            # Load sentiment analysis model (CardiffNLP XLM-RoBERTa - Multilingual)
            # This model classifies sentiment into: negative, neutral, positive
            # Supports multiple languages including English, Spanish, French, German, etc.
            logger.info("Loading multilingual sentiment analyzer...")
            self.sentiment_analyzer = pipeline(
                "sentiment-analysis",
                model="cardiffnlp/twitter-xlm-roberta-base-sentiment",
                device=device
            )
            
            logger.success("NLP models loaded successfully (Emotion: English-only, Sentiment: Multilingual)")
            
        except Exception as e:
            logger.error(f"Failed to load NLP models: {e}")
            raise
    
    def analyze_text(self, text: str) -> Dict:
        """
        Analyze a single text for emotion and sentiment
        
        Args:
            text: The text to analyze
            
        Returns:
            Dictionary with emotion and sentiment analysis results
        """
        if not text or not text.strip():
            return {
                'text': text,
                'emotions': {},
                'primary_emotion': None,
                'sentiment': None,
                'sentiment_score': 0.0,
                'distortion_indicator': False
            }
        
        try:
            # Truncate text if too long (RoBERTa max length is 512 tokens)
            text = text[:500] if len(text) > 500 else text
            
            # Get emotion analysis
            emotion_results = self.emotion_analyzer(text)
            
            # Convert emotion results to dict with scores
            emotions = {}
            for result in emotion_results[0]:
                emotions[result['label']] = result['score']
            
            # Get primary emotion (highest score)
            primary_emotion = max(emotions.items(), key=lambda x: x[1])
            
            # Get sentiment analysis
            sentiment_result = self.sentiment_analyzer(text)[0]
            
            # Advanced cognitive distortion analysis
            cognitive_analysis = self.pattern_service.detect_cognitive_distortions(text)
            
            # Calculate distortion indicator (use advanced analysis + basic emotion scoring)
            distortion_emotions = ['sadness', 'anger', 'fear']
            emotion_distortion_score = sum(
                emotions.get(emotion, 0) for emotion in distortion_emotions
            )
            
            # Combine cognitive distortions with emotional indicators
            combined_distortion = max(
                cognitive_analysis['distortion_ratio'] / 20,  # Normalize to 0-1 scale
                emotion_distortion_score
            )
            distortion_indicator = combined_distortion > 0.5 or cognitive_analysis['has_distortions']
            
            return {
                'text': text,
                'emotions': emotions,
                'primary_emotion': primary_emotion[0],
                'primary_emotion_score': primary_emotion[1],
                'sentiment': sentiment_result['label'],
                'sentiment_score': sentiment_result['score'],
                'distortion_indicator': distortion_indicator,
                'distortion_score': float(combined_distortion),
                'cognitive_distortions': cognitive_analysis,
                'risk_indicators': {
                    'high_negative_emotions': emotion_distortion_score > 0.7,
                    'cognitive_distortions_present': cognitive_analysis['has_distortions'],
                    'distortion_ratio': cognitive_analysis['distortion_ratio']
                }
            }
            
        except Exception as e:
            logger.error(f"Error analyzing text: {e}")
            return {
                'text': text,
                'emotions': {},
                'primary_emotion': None,
                'sentiment': None,
                'sentiment_score': 0.0,
                'distortion_indicator': False,
                'error': str(e)
            }
    
    async def analyze_comments_from_posts(
        self, 
        usernames: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Analyze comments from posts in the database
        
        Args:
            usernames: Optional list of usernames to filter posts
            limit: Optional limit on number of posts to process
            
        Returns:
            List of analyzed comments with NLP results
        """
        try:
            posts_collection = await get_posts_collection()
            
            # Build query
            query = {}
            if usernames:
                query['username'] = {'$in': usernames}
            
            # Get posts with comments
            posts_cursor = posts_collection.find(
                {**query, 'comments': {'$exists': True, '$ne': []}}
            )
            
            if limit:
                posts_cursor = posts_cursor.limit(limit)
            
            analyzed_comments = []
            
            async for post in posts_cursor:
                comments = post.get('comments', [])
                post_shortcode = post.get('shortcode', 'unknown')
                post_username = post.get('username', 'unknown')
                
                for comment in comments:
                    comment_text = comment.get('text', '')
                    commenter = comment.get('owner', 'unknown')
                    
                    if not comment_text:
                        continue
                    
                    # Analyze the comment text
                    analysis = self.analyze_text(comment_text)
                    
                    # Add metadata
                    analysis.update({
                        'user': commenter,
                        'comment_id': comment.get('id'),
                        'post_shortcode': post_shortcode,
                        'post_owner': post_username,
                        'comment_created_at': comment.get('created_at'),
                        'likes': comment.get('likes', 0)
                    })
                    
                    analyzed_comments.append(analysis)
            
            logger.info(f"Analyzed {len(analyzed_comments)} comments")
            return analyzed_comments
            
        except Exception as e:
            logger.error(f"Error analyzing comments from posts: {e}")
            raise
    
    async def analyze_comment_users(
        self,
        usernames: Optional[List[str]] = None,
        min_comments: int = 1
    ) -> List[Dict]:
        """
        Analyze all comments from comment users collection
        
        Args:
            usernames: Optional list of usernames to filter
            min_comments: Minimum number of comments a user must have
            
        Returns:
            List of analyzed comments with NLP results
        """
        try:
            comment_users_collection = await get_comment_users_collection()
            
            # Build query
            query = {}
            if usernames:
                query['username'] = {'$in': usernames}
            if min_comments > 1:
                query['total_comments'] = {'$gte': min_comments}
            
            analyzed_comments = []
            
            async for user in comment_users_collection.find(query):
                username = user.get('username', 'unknown')
                comments = user.get('comments', [])
                
                for comment in comments:
                    comment_text = comment.get('text', '')
                    
                    if not comment_text:
                        continue
                    
                    # Analyze the comment text
                    analysis = self.analyze_text(comment_text)
                    
                    # Add metadata
                    analysis.update({
                        'user': username,
                        'comment_id': comment.get('comment_id'),
                        'post_shortcode': comment.get('post_shortcode'),
                        'comment_created_at': comment.get('created_at'),
                        'likes': comment.get('likes', 0)
                    })
                    
                    analyzed_comments.append(analysis)
            
            logger.info(f"Analyzed {len(analyzed_comments)} comments from comment users")
            return analyzed_comments
            
        except Exception as e:
            logger.error(f"Error analyzing comment users: {e}")
            raise
    
    def create_signal_dataframe(self, analyzed_comments: List[Dict]) -> pd.DataFrame:
        """
        Create a Signal DataFrame from analyzed comments
        
        Args:
            analyzed_comments: List of analyzed comment dictionaries
            
        Returns:
            Pandas DataFrame with signal data
        """
        if not analyzed_comments:
            return pd.DataFrame()
        
        # Extract relevant fields for the signal CSV
        signal_data = []
        
        for comment in analyzed_comments:
            signal_data.append({
                'User': comment.get('user', 'unknown'),
                'Comment_Text': comment.get('text', ''),
                'Emotion_Label': comment.get('primary_emotion', 'unknown'),
                'Emotion_Score': comment.get('primary_emotion_score', 0.0),
                'Sentiment': comment.get('sentiment', 'unknown'),
                'Sentiment_Score': comment.get('sentiment_score', 0.0),
                'Distortion_Indicator': comment.get('distortion_indicator', False),
                'Distortion_Score': comment.get('distortion_score', 0.0),
                'Sadness_Score': comment.get('emotions', {}).get('sadness', 0.0),
                'Anger_Score': comment.get('emotions', {}).get('anger', 0.0),
                'Fear_Score': comment.get('emotions', {}).get('fear', 0.0),
                'Joy_Score': comment.get('emotions', {}).get('joy', 0.0),
                'Love_Score': comment.get('emotions', {}).get('love', 0.0),
                'Surprise_Score': comment.get('emotions', {}).get('surprise', 0.0),
                'Post_Shortcode': comment.get('post_shortcode', ''),
                'Post_Owner': comment.get('post_owner', ''),
                'Comment_ID': comment.get('comment_id', ''),
                'Comment_Likes': comment.get('likes', 0),
                'Comment_Created_At': comment.get('comment_created_at', ''),
            })
        
        df = pd.DataFrame(signal_data)
        
        # Sort by distortion score (highest first) to prioritize concerning comments
        df = df.sort_values('Distortion_Score', ascending=False)
        
        return df
    
    async def export_signal_csv(
        self,
        output_path: str,
        usernames: Optional[List[str]] = None,
        source: str = "posts",  # "posts" or "comment_users"
        limit: Optional[int] = None
    ) -> str:
        """
        Export signal data to CSV file
        
        Args:
            output_path: Path to save the CSV file
            usernames: Optional list of usernames to filter
            source: Source of comments ("posts" or "comment_users")
            limit: Optional limit on number of posts to process
            
        Returns:
            Path to the created CSV file
        """
        try:
            # Get analyzed comments
            if source == "posts":
                analyzed_comments = await self.analyze_comments_from_posts(
                    usernames=usernames,
                    limit=limit
                )
            else:
                analyzed_comments = await self.analyze_comment_users(
                    usernames=usernames
                )
            
            # Create DataFrame
            df = self.create_signal_dataframe(analyzed_comments)
            
            # Save to CSV
            df.to_csv(output_path, index=False)
            
            logger.success(f"Signal CSV exported to {output_path} with {len(df)} rows")
            return output_path
            
        except Exception as e:
            logger.error(f"Error exporting signal CSV: {e}")
            raise


# Global instance
nlp_service = None

def get_nlp_service() -> NLPService:
    """Get or create NLP service instance"""
    global nlp_service
    if nlp_service is None:
        nlp_service = NLPService()
    return nlp_service
