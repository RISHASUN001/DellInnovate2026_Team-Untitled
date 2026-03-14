"""
Stage 2: Behavioral Feature Engineering

This module implements the second stage of the analytics pipeline:
1. Aggregate NLP signals per case user over time windows
2. Compute cognitive distortion metrics
3. Analyze sentiment volatility
4. Detect engagement pattern changes
5. Calculate risk scores and prioritization
6. Store risk profiles in case_risk_profiles collection
"""

import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import numpy as np
from collections import Counter
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient

from config.database import MongoDB
from models.instagram_models import CaseRiskProfileModel


class BehavioralFeatureEngineer:
    """
    Stage 2: Behavioral Feature Engineering and Risk Scoring
    """
    
    def __init__(self, db_client: AsyncIOMotorClient = None):
        """
        Initialize feature engineer
        
        Args:
            db_client: MongoDB client (uses default if None)
        """
        self.db = db_client if db_client is not None else MongoDB.get_db()
        logger.info("Behavioral Feature Engineer initialized")
    
    async def get_case_users(self) -> List[str]:
        """
        Get list of all case users from signals collection
        
        Returns:
            List of unique case usernames
        """
        signals_collection = self.db.text_units_signals
        case_users = await signals_collection.distinct('case_user')
        return case_users
    
    async def fetch_signals_for_user(self,
                                     case_user: str,
                                     window_days: int = 7) -> List[Dict]:
        """
        Fetch NLP signals for a case user within time window
        
        Args:
            case_user: Username to fetch signals for
            window_days: Number of days to look back
            
        Returns:
            List of signal documents
        """
        signals_collection = self.db.text_units_signals
        
        window_start = datetime.utcnow() - timedelta(days=window_days)
        
        query = {
            'case_user': case_user,
            'processed_at': {'$gte': window_start}
        }
        
        signals = await signals_collection.find(query).to_list(length=None)
        return signals
    
    def compute_distortion_metrics(self, signals: List[Dict]) -> Dict:
        """
        Compute cognitive distortion metrics
        
        Args:
            signals: List of signal documents
            
        Returns:
            Dict with distortion metrics
        """
        total_signals = len(signals)
        if total_signals == 0:
            return {
                'distortion_count': 0,
                'distortion_rate': 0.0,
                'distortion_categories': {}
            }
        
        distorted_signals = [s for s in signals if s.get('distortion_indicator', 0) == 1]
        distortion_count = len(distorted_signals)
        distortion_rate = distortion_count / total_signals
        
        # Count by category
        categories = [s.get('distortion_category') for s in distorted_signals 
                     if s.get('distortion_category')]
        category_counts = dict(Counter(categories))
        
        return {
            'distortion_count': distortion_count,
            'distortion_rate': distortion_rate,
            'distortion_categories': category_counts
        }
    
    def compute_sentiment_metrics(self, signals: List[Dict]) -> Dict:
        """
        Compute sentiment volatility and trends
        
        Args:
            signals: List of signal documents
            
        Returns:
            Dict with sentiment metrics
        """
        sentiment_scores = [s.get('sentiment_score', 0.0) for s in signals]
        
        if not sentiment_scores:
            return {
                'avg_sentiment_score': 0.0,
                'sentiment_std': 0.0,
                'negative_sentiment_rate': 0.0,
                'positive_sentiment_rate': 0.0
            }
        
        # Basic statistics
        avg_sentiment = np.mean(sentiment_scores)
        sentiment_std = np.std(sentiment_scores)
        
        # Count sentiment labels
        negative_count = sum(1 for s in signals if s.get('sentiment_label') == 'negative')
        positive_count = sum(1 for s in signals if s.get('sentiment_label') == 'positive')
        total = len(signals)
        
        return {
            'avg_sentiment_score': float(avg_sentiment),
            'sentiment_std': float(sentiment_std),
            'negative_sentiment_rate': negative_count / total if total > 0 else 0.0,
            'positive_sentiment_rate': positive_count / total if total > 0 else 0.0
        }
    
    def compute_emotion_metrics(self, signals: List[Dict]) -> Dict:
        """
        Compute emotion distribution and distress metrics
        
        Args:
            signals: List of signal documents
            
        Returns:
            Dict with emotion metrics
        """
        if not signals:
            return {
                'distress_emotion_count': 0,
                'distress_emotion_rate': 0.0,
                'emotion_distribution': {},
                'avg_distress_score': 0.0
            }
        
        # Count distress emotions
        distress_count = sum(1 for s in signals if s.get('is_distress', False))
        distress_rate = distress_count / len(signals)
        
        # Emotion distribution
        emotions = [s.get('emotion_label', 'neutral') for s in signals]
        emotion_dist = dict(Counter(emotions))
        
        # Average distress score
        distress_scores = [s.get('distress_score', 0.0) for s in signals]
        avg_distress = np.mean(distress_scores) if distress_scores else 0.0
        
        return {
            'distress_emotion_count': distress_count,
            'distress_emotion_rate': distress_rate,
            'emotion_distribution': emotion_dist,
            'avg_distress_score': float(avg_distress)
        }
    
    def compute_engagement_metrics(self, signals: List[Dict]) -> Dict:
        """
        Analyze engagement patterns
        
        Args:
            signals: List of signal documents
            
        Returns:
            Dict with engagement metrics
        """
        comments = [s for s in signals if s.get('text_type') == 'comment']
        comment_volume = len(comments)
        
        # Detect late-night activity (11 PM - 2 AM)
        late_night_count = 0
        for signal in signals:
            timestamp = signal.get('timestamp')
            if timestamp and isinstance(timestamp, datetime):
                hour = timestamp.hour
                if 23 <= hour or hour <= 2:
                    late_night_count += 1
        
        late_night_rate = late_night_count / len(signals) if signals else 0.0
        
        # Flag abnormal activity (simple heuristic: more than 20 comments)
        abnormal_activity = comment_volume > 20
        
        return {
            'comment_volume': comment_volume,
            'late_night_activity_rate': late_night_rate,
            'abnormal_activity': abnormal_activity
        }
    
    def calculate_risk_score(self,
                            distortion_metrics: Dict,
                            sentiment_metrics: Dict,
                            emotion_metrics: Dict,
                            engagement_metrics: Dict) -> Dict:
        """
        Calculate composite risk score and priority level
        
        Scoring weights:
        - Distortion rate: 25%
        - Sentiment volatility: 20%
        - Negative sentiment: 15%
        - Distress emotions: 25%
        - Engagement abnormality: 15%
        
        Args:
            distortion_metrics: Distortion analysis results
            sentiment_metrics: Sentiment analysis results
            emotion_metrics: Emotion analysis results
            engagement_metrics: Engagement analysis results
            
        Returns:
            Dict with risk_score, risk_level, priority
        """
        # Component scores (0-100)
        distortion_score = min(distortion_metrics['distortion_rate'] * 200, 100)
        
        sentiment_volatility_score = min(sentiment_metrics['sentiment_std'] * 100, 100)
        
        negative_sentiment_score = sentiment_metrics['negative_sentiment_rate'] * 100
        
        distress_emotion_score = emotion_metrics['distress_emotion_rate'] * 100
        
        engagement_score = 100 if engagement_metrics['abnormal_activity'] else 0
        
        # Weighted composite score
        risk_score = (
            distortion_score * 0.25 +
            sentiment_volatility_score * 0.20 +
            negative_sentiment_score * 0.15 +
            distress_emotion_score * 0.25 +
            engagement_score * 0.15
        )
        
        # Determine risk level and priority
        if risk_score >= 70:
            risk_level = "High"
            priority = 1
        elif risk_score >= 40:
            risk_level = "Medium"
            priority = 2
        else:
            risk_level = "Low"
            priority = 3
        
        return {
            'risk_score': float(risk_score),
            'risk_level': risk_level,
            'priority': priority,
            'component_scores': {
                'distortion': float(distortion_score),
                'sentiment_volatility': float(sentiment_volatility_score),
                'negative_sentiment': float(negative_sentiment_score),
                'distress_emotion': float(distress_emotion_score),
                'engagement_abnormality': float(engagement_score)
            }
        }
    
    def extract_evidence(self, signals: List[Dict], max_samples: int = 5) -> Dict:
        """
        Extract supporting evidence for the risk assessment
        
        Args:
            signals: List of signal documents
            max_samples: Maximum number of sample comments to include
            
        Returns:
            Dict with evidence samples and key signals
        """
        # Get most concerning comments (high distress, high distortion)
        scored_signals = []
        for signal in signals:
            concern_score = (
                signal.get('distress_score', 0.0) * 0.5 +
                signal.get('distortion_indicator', 0) * 50 +
                (1.0 - signal.get('sentiment_score', 0.0)) * 25
            )
            scored_signals.append((concern_score, signal))
        
        scored_signals.sort(reverse=True, key=lambda x: x[0])
        
        # Extract top comments
        top_comments = []
        for score, signal in scored_signals[:max_samples]:
            text = signal.get('text', '')
            if len(text) > 100:
                text = text[:97] + "..."
            top_comments.append(text)
        
        # Generate key signal descriptions
        distortion_metrics = self.compute_distortion_metrics(signals)
        sentiment_metrics = self.compute_sentiment_metrics(signals)
        emotion_metrics = self.compute_emotion_metrics(signals)
        
        key_signals = []
        
        if distortion_metrics['distortion_rate'] > 0.2:
            key_signals.append(
                f"High cognitive distortion rate: {distortion_metrics['distortion_rate']:.1%}"
            )
        
        if sentiment_metrics['sentiment_std'] > 0.5:
            key_signals.append(
                f"High sentiment volatility: σ={sentiment_metrics['sentiment_std']:.2f}"
            )
        
        if emotion_metrics['distress_emotion_rate'] > 0.3:
            key_signals.append(
                f"Elevated distress emotions: {emotion_metrics['distress_emotion_rate']:.1%}"
            )
        
        if sentiment_metrics['negative_sentiment_rate'] > 0.4:
            key_signals.append(
                f"High negative sentiment rate: {sentiment_metrics['negative_sentiment_rate']:.1%}"
            )
        
        return {
            'top_distress_comments': top_comments,
            'key_signals': key_signals
        }
    
    async def compute_risk_profile(self, 
                                   case_user: str,
                                   window_days: int = 7) -> Optional[Dict]:
        """
        Compute complete risk profile for a case user
        
        Args:
            case_user: Username to analyze
            window_days: Time window in days
            
        Returns:
            Risk profile document ready for MongoDB
        """
        logger.info(f"Computing risk profile for {case_user} (window: {window_days} days)")
        
        # Fetch signals
        signals = await self.fetch_signals_for_user(case_user, window_days)
        
        if not signals:
            logger.warning(f"No signals found for {case_user}")
            return None
        
        window_end = datetime.utcnow()
        window_start = window_end - timedelta(days=window_days)
        
        # Count text types
        comments = [s for s in signals if s.get('text_type') == 'comment']
        captions = [s for s in signals if s.get('text_type') == 'caption']
        
        # Compute all metrics
        distortion_metrics = self.compute_distortion_metrics(signals)
        sentiment_metrics = self.compute_sentiment_metrics(signals)
        emotion_metrics = self.compute_emotion_metrics(signals)
        engagement_metrics = self.compute_engagement_metrics(signals)
        risk_metrics = self.calculate_risk_score(
            distortion_metrics, sentiment_metrics, emotion_metrics, engagement_metrics
        )
        evidence = self.extract_evidence(signals)
        
        # Create risk profile document
        profile = {
            'case_user': case_user,
            'analysis_window_days': window_days,
            'window_start': window_start,
            'window_end': window_end,
            
            'total_comments_received': len(comments),
            'total_captions': len(captions),
            'total_text_units': len(signals),
            
            'distortion_count': distortion_metrics['distortion_count'],
            'distortion_rate': distortion_metrics['distortion_rate'],
            'distortion_categories': distortion_metrics['distortion_categories'],
            
            'avg_sentiment_score': sentiment_metrics['avg_sentiment_score'],
            'sentiment_std': sentiment_metrics['sentiment_std'],
            'negative_sentiment_rate': sentiment_metrics['negative_sentiment_rate'],
            'positive_sentiment_rate': sentiment_metrics['positive_sentiment_rate'],
            
            'distress_emotion_count': emotion_metrics['distress_emotion_count'],
            'distress_emotion_rate': emotion_metrics['distress_emotion_rate'],
            'emotion_distribution': emotion_metrics['emotion_distribution'],
            'avg_distress_score': emotion_metrics['avg_distress_score'],
            
            'abnormal_activity': engagement_metrics['abnormal_activity'],
            'late_night_activity_rate': engagement_metrics.get('late_night_activity_rate'),
            
            'risk_score': risk_metrics['risk_score'],
            'risk_level': risk_metrics['risk_level'],
            'priority': risk_metrics['priority'],
            
            'top_distress_comments': evidence['top_distress_comments'],
            'key_signals': evidence['key_signals'],
            
            'computed_at': datetime.utcnow(),
            'last_updated': datetime.utcnow()
        }
        
        logger.success(
            f"Risk profile computed for {case_user}: "
            f"Score={risk_metrics['risk_score']:.1f}, Level={risk_metrics['risk_level']}"
        )
        
        return profile
    
    async def store_risk_profile(self, profile: Dict) -> str:
        """
        Store or update risk profile in MongoDB
        
        Args:
            profile: Risk profile document
            
        Returns:
            Profile ID
        """
        profiles_collection = self.db.case_risk_profiles
        
        # Upsert: update if exists, insert if not
        result = await profiles_collection.update_one(
            {'case_user': profile['case_user']},
            {'$set': profile},
            upsert=True
        )
        
        profile_id = str(result.upserted_id) if result.upserted_id else "updated"
        logger.info(f"Risk profile stored: {profile_id}")
        
        return profile_id
    
    async def run_pipeline(self,
                          case_users: Optional[List[str]] = None,
                          window_days: int = 7) -> Dict:
        """
        Run complete Stage 2 Behavioral Feature Engineering Pipeline
        
        Args:
            case_users: Specific users to process (None = all)
            window_days: Time window for analysis
            
        Returns:
            Pipeline execution results
        """
        start_time = datetime.utcnow()
        logger.info("=" * 70)
        logger.info("Starting Behavioral Feature Engineering Pipeline (Stage 2)")
        logger.info("=" * 70)
        
        # Get case users
        if not case_users:
            logger.info("Fetching all case users from signals...")
            case_users = await self.get_case_users()
        
        logger.info(f"Processing {len(case_users)} case users...")
        
        # Process each user
        profiles_created = 0
        high_risk_cases = []
        
        for i, case_user in enumerate(case_users, 1):
            logger.info(f"[{i}/{len(case_users)}] Processing {case_user}...")
            
            try:
                profile = await self.compute_risk_profile(case_user, window_days)
                
                if profile:
                    await self.store_risk_profile(profile)
                    profiles_created += 1
                    
                    if profile['risk_level'] == 'High':
                        high_risk_cases.append(case_user)
            
            except Exception as e:
                logger.error(f"Error processing {case_user}: {e}")
                continue
        
        # Calculate duration
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info("=" * 70)
        logger.success(f"Pipeline completed in {duration:.2f} seconds")
        logger.info(f"Case users processed: {len(case_users)}")
        logger.info(f"Risk profiles created: {profiles_created}")
        logger.info(f"High-risk cases identified: {len(high_risk_cases)}")
        if high_risk_cases:
            logger.warning(f"High-risk users: {', '.join(high_risk_cases)}")
        logger.info("=" * 70)
        
        return {
            'status': 'completed',
            'case_users_processed': len(case_users),
            'profiles_created': profiles_created,
            'high_risk_cases': high_risk_cases,
            'duration_seconds': duration
        }


async def run_feature_engineering(case_users: Optional[List[str]] = None,
                                 window_days: int = 7) -> Dict:
    """
    Convenience function to run feature engineering pipeline
    
    Args:
        case_users: Specific users to process
        window_days: Analysis time window
        
    Returns:
        Pipeline results
    """
    engineer = BehavioralFeatureEngineer()
    return await engineer.run_pipeline(case_users=case_users, window_days=window_days)
