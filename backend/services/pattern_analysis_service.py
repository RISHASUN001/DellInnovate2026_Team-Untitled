"""
Pattern Analysis Service - Stage 2 of NLP Pipeline
Analyzes cognitive distortions, sentiment volatility, and engagement patterns
"""
from typing import Dict, List, Optional
import pandas as pd
import re
from datetime import datetime
from loguru import logger
from collections import defaultdict
import numpy as np


class PatternAnalysisService:
    """Service for advanced pattern analysis on NLP results"""
    
    # Cognitive Distortion Patterns (keyword-based detection)
    DISTORTION_PATTERNS = {
        'all_or_nothing': {
            'patterns': [
                r'\b(always|never|every|all|nothing|none|everyone|no one|nobody)\b',
                r'\b(completely|totally|absolutely|entirely)\b',
                r'\b(perfect|terrible|horrible|awful)\b'
            ],
            'description': 'Black-and-white thinking with no middle ground'
        },
        'overgeneralization': {
            'patterns': [
                r'\b(everything|everyone|all the time|constantly|forever)\b',
                r'\b(typical|usual|always happens)\b',
                r'\b(every time|each time)\b'
            ],
            'description': 'Drawing broad conclusions from single events'
        },
        'catastrophizing': {
            'patterns': [
                r'\b(disaster|catastrophe|terrible|horrible|worst|nightmare)\b',
                r'\b(never going to|impossible|hopeless|doomed)\b',
                r'\b(end of|ruined|destroyed|devastating)\b',
                r'\b(what if .* wrong|what if .* happens)\b'
            ],
            'description': 'Expecting the worst possible outcome'
        },
        'personalization': {
            'patterns': [
                r'\b(my fault|I caused|because of me|I\'m to blame)\b',
                r'\b(I should have|I could have|if only I)\b',
                r'\b(I ruined|I destroyed|I messed up)\b'
            ],
            'description': 'Taking personal responsibility for external events'
        },
        'emotional_reasoning': {
            'patterns': [
                r'\bI feel .* so it must be\b',
                r'\b(feels like|seems like) .* is\b',
                r'\bI know .* because I feel\b'
            ],
            'description': 'Assuming feelings reflect reality'
        },
        'should_statements': {
            'patterns': [
                r'\b(should|shouldn\'t|must|have to|need to|ought to)\b',
                r'\b(supposed to|expected to|required to)\b'
            ],
            'description': 'Rigid rules about how things ought to be'
        },
        'labeling': {
            'patterns': [
                r'\bI\'m (a|an) .*(loser|failure|idiot|stupid|worthless|useless)\b',
                r'\bI am .*(pathetic|weak|broken|damaged)\b',
                r'\b(everyone|they) (is|are) .*(terrible|awful|horrible)\b'
            ],
            'description': 'Assigning global negative labels to self or others'
        },
        'mental_filtering': {
            'patterns': [
                r'\bonly .*(bad|negative|wrong|terrible)\b',
                r'\bnothing .*(good|positive|right)\b',
                r'\ball I see is .*(problems|issues|negativity)\b'
            ],
            'description': 'Focusing exclusively on negative details'
        }
    }
    
    def __init__(self):
        """Initialize Pattern Analysis Service"""
        logger.info("Pattern Analysis Service initialized")
    
    def detect_cognitive_distortions(self, text: str) -> Dict:
        """
        Detect cognitive distortion patterns in text
        
        Args:
            text: The text to analyze
            
        Returns:
            Dictionary with distortion types and counts
        """
        text_lower = text.lower()
        distortions = {}
        total_matches = 0
        
        for distortion_type, config in self.DISTORTION_PATTERNS.items():
            matches = 0
            for pattern in config['patterns']:
                matches += len(re.findall(pattern, text_lower, re.IGNORECASE))
            
            distortions[distortion_type] = {
                'count': matches,
                'description': config['description']
            }
            total_matches += matches
        
        # Calculate distortion ratio (matches per 100 words)
        word_count = len(text.split())
        distortion_ratio = (total_matches / word_count * 100) if word_count > 0 else 0
        
        # Determine primary distortion type
        primary_distortion = max(distortions.items(), key=lambda x: x[1]['count'])
        
        return {
            'total_distortions': total_matches,
            'distortion_ratio': distortion_ratio,
            'word_count': word_count,
            'distortions': distortions,
            'primary_distortion': primary_distortion[0] if primary_distortion[1]['count'] > 0 else None,
            'has_distortions': total_matches > 0
        }
    
    def analyze_sentiment_volatility(
        self,
        user_comments: List[Dict],
        window_size: int = 3
    ) -> Dict:
        """
        Analyze sentiment volatility (rapid emotional shifts) for a user
        
        Args:
            user_comments: List of analyzed comments for a single user (must be sorted by time)
            window_size: Number of comments to consider for volatility window
            
        Returns:
            Dictionary with volatility metrics
        """
        if len(user_comments) < 2:
            return {
                'volatility_score': 0.0,
                'mean_sentiment': 0.0,
                'sentiment_std': 0.0,
                'rapid_shifts': 0,
                'total_comments': len(user_comments),
                'risk_level': 'insufficient_data'
            }
        
        # Extract sentiment scores (convert to -1 to 1 scale)
        sentiment_scores = []
        for comment in user_comments:
            score = comment.get('sentiment_score', 0.5)
            sentiment = comment.get('sentiment', 'neutral')
            
            # Convert to -1 to 1 scale
            if sentiment == 'positive':
                normalized_score = score
            elif sentiment == 'negative':
                normalized_score = -score
            else:
                normalized_score = 0.0
            
            sentiment_scores.append(normalized_score)
        
        sentiment_array = np.array(sentiment_scores)
        
        # Calculate metrics
        mean_sentiment = np.mean(sentiment_array)
        sentiment_std = np.std(sentiment_array)
        
        # Calculate volatility (average absolute change between consecutive comments)
        changes = np.abs(np.diff(sentiment_array))
        volatility_score = np.mean(changes) if len(changes) > 0 else 0.0
        
        # Detect rapid shifts (changes > 1.0 on -1 to 1 scale)
        rapid_shifts = np.sum(changes > 1.0)
        
        # Calculate windowed volatility
        windowed_volatility = []
        for i in range(len(sentiment_array) - window_size + 1):
            window = sentiment_array[i:i + window_size]
            window_std = np.std(window)
            windowed_volatility.append(window_std)
        
        max_window_volatility = max(windowed_volatility) if windowed_volatility else 0.0
        
        # Determine risk level
        if volatility_score > 1.2 or rapid_shifts >= 3:
            risk_level = 'high'
        elif volatility_score > 0.8 or rapid_shifts >= 2:
            risk_level = 'medium'
        elif volatility_score > 0.5 or rapid_shifts >= 1:
            risk_level = 'low'
        else:
            risk_level = 'stable'
        
        return {
            'volatility_score': float(volatility_score),
            'mean_sentiment': float(mean_sentiment),
            'sentiment_std': float(sentiment_std),
            'rapid_shifts': int(rapid_shifts),
            'max_window_volatility': float(max_window_volatility),
            'total_comments': len(user_comments),
            'risk_level': risk_level,
            'sentiment_trend': 'declining' if mean_sentiment < -0.3 else 'improving' if mean_sentiment > 0.3 else 'neutral'
        }
    
    def analyze_engagement_patterns(
        self,
        user_comments: List[Dict],
        time_field: str = 'comment_created_at'
    ) -> Dict:
        """
        Analyze user engagement patterns and behavioral changes
        
        Args:
            user_comments: List of analyzed comments for a single user
            time_field: Field name containing timestamp
            
        Returns:
            Dictionary with engagement metrics
        """
        if not user_comments:
            return {
                'total_comments': 0,
                'engagement_score': 0.0,
                'pattern': 'no_data'
            }
        
        total_comments = len(user_comments)
        
        # Parse timestamps
        timestamps = []
        for comment in user_comments:
            time_str = comment.get(time_field)
            if time_str:
                try:
                    timestamps.append(datetime.fromisoformat(time_str.replace('Z', '+00:00')))
                except:
                    pass
        
        # Calculate time-based metrics
        if len(timestamps) >= 2:
            timestamps.sort()
            time_span = (timestamps[-1] - timestamps[0]).total_seconds() / 3600  # hours
            
            # Calculate average time between comments
            time_diffs = [(timestamps[i+1] - timestamps[i]).total_seconds() / 3600 
                         for i in range(len(timestamps) - 1)]
            avg_time_between = np.mean(time_diffs) if time_diffs else 0
            std_time_between = np.std(time_diffs) if time_diffs else 0
            
            # Detect bursts (multiple comments in short time)
            burst_threshold = 1.0  # 1 hour
            bursts = sum(1 for diff in time_diffs if diff < burst_threshold)
            
            # Detect long gaps (unusual silence)
            gap_threshold = avg_time_between * 2 if avg_time_between > 0 else 24
            long_gaps = sum(1 for diff in time_diffs if diff > gap_threshold)
        else:
            time_span = 0
            avg_time_between = 0
            std_time_between = 0
            bursts = 0
            long_gaps = 0
        
        # Calculate engagement intensity metrics
        total_likes = sum(comment.get('likes', 0) for comment in user_comments)
        avg_likes = total_likes / total_comments if total_comments > 0 else 0
        
        # Word count analysis
        word_counts = [len(comment.get('text', '').split()) for comment in user_comments]
        avg_words = np.mean(word_counts) if word_counts else 0
        
        # Distortion analysis
        high_distortion_count = sum(1 for c in user_comments if c.get('distortion_indicator', False))
        distortion_rate = high_distortion_count / total_comments if total_comments > 0 else 0
        
        # Overall engagement score (0-100)
        engagement_score = min(100, (
            (total_comments * 5) +  # Activity
            (avg_likes * 2) +  # Community response
            (bursts * 10) -  # Burst activity (can indicate crisis)
            (long_gaps * 5) -  # Disengagement periods
            (distortion_rate * 30)  # Mental state concerns
        ))
        
        # Determine pattern
        if bursts >= 3 and distortion_rate > 0.5:
            pattern = 'crisis_burst'
        elif long_gaps >= 2 and distortion_rate > 0.3:
            pattern = 'declining_engagement'
        elif avg_time_between < 2 and total_comments > 10:
            pattern = 'high_activity'
        elif distortion_rate > 0.6:
            pattern = 'concerning_content'
        elif total_comments >= 5 and distortion_rate < 0.2:
            pattern = 'healthy_engagement'
        else:
            pattern = 'normal'
        
        return {
            'total_comments': total_comments,
            'time_span_hours': float(time_span),
            'avg_time_between_hours': float(avg_time_between),
            'std_time_between_hours': float(std_time_between),
            'comment_bursts': bursts,
            'long_gaps': long_gaps,
            'total_likes': total_likes,
            'avg_likes_per_comment': float(avg_likes),
            'avg_words_per_comment': float(avg_words),
            'high_distortion_count': high_distortion_count,
            'distortion_rate': float(distortion_rate),
            'engagement_score': float(engagement_score),
            'pattern': pattern,
            'risk_indicators': {
                'frequent_bursts': bursts >= 3,
                'long_silence': long_gaps >= 2,
                'high_distortion': distortion_rate > 0.5,
                'declining_engagement': long_gaps >= 2 and distortion_rate > 0.3
            }
        }
    
    def analyze_user_comprehensive(
        self,
        user_comments: List[Dict],
        username: str
    ) -> Dict:
        """
        Comprehensive analysis combining all pattern analysis methods
        
        Args:
            user_comments: List of analyzed comments for a single user
            username: Username for identification
            
        Returns:
            Complete analysis results
        """
        # Sort by timestamp
        user_comments_sorted = sorted(
            user_comments,
            key=lambda x: x.get('comment_created_at', ''),
            reverse=False
        )
        
        # Analyze each comment for cognitive distortions
        for comment in user_comments_sorted:
            text = comment.get('text', '')
            distortion_analysis = self.detect_cognitive_distortions(text)
            comment['cognitive_distortions'] = distortion_analysis
        
        # Calculate aggregate distortion metrics
        total_distortions = sum(c['cognitive_distortions']['total_distortions'] for c in user_comments_sorted)
        avg_distortion_ratio = np.mean([c['cognitive_distortions']['distortion_ratio'] for c in user_comments_sorted])
        
        # Sentiment volatility analysis
        volatility = self.analyze_sentiment_volatility(user_comments_sorted)
        
        # Engagement pattern analysis
        engagement = self.analyze_engagement_patterns(user_comments_sorted)
        
        # Overall risk assessment
        risk_factors = []
        risk_score = 0
        
        if volatility['risk_level'] == 'high':
            risk_factors.append('High sentiment volatility')
            risk_score += 30
        elif volatility['risk_level'] == 'medium':
            risk_factors.append('Moderate sentiment volatility')
            risk_score += 15
        
        if engagement['distortion_rate'] > 0.5:
            risk_factors.append('High cognitive distortion rate')
            risk_score += 25
        
        if engagement['pattern'] == 'crisis_burst':
            risk_factors.append('Crisis burst pattern detected')
            risk_score += 30
        elif engagement['pattern'] == 'declining_engagement':
            risk_factors.append('Declining engagement pattern')
            risk_score += 20
        
        if volatility['rapid_shifts'] >= 3:
            risk_factors.append('Multiple rapid emotional shifts')
            risk_score += 15
        
        # Determine overall risk level
        if risk_score >= 50:
            overall_risk = 'high'
        elif risk_score >= 30:
            overall_risk = 'medium'
        elif risk_score >= 15:
            overall_risk = 'low'
        else:
            overall_risk = 'minimal'
        
        return {
            'username': username,
            'total_comments_analyzed': len(user_comments_sorted),
            'cognitive_distortions': {
                'total_distortions': total_distortions,
                'avg_distortion_ratio': float(avg_distortion_ratio),
                'comments_with_distortions': sum(1 for c in user_comments_sorted if c['cognitive_distortions']['has_distortions'])
            },
            'sentiment_volatility': volatility,
            'engagement_patterns': engagement,
            'risk_assessment': {
                'overall_risk_level': overall_risk,
                'risk_score': risk_score,
                'risk_factors': risk_factors,
                'requires_attention': overall_risk in ['high', 'medium']
            },
            'recommendations': self._generate_recommendations(overall_risk, risk_factors, engagement['pattern'])
        }
    
    def _generate_recommendations(self, risk_level: str, risk_factors: List[str], pattern: str) -> List[str]:
        """Generate recommendations based on analysis"""
        recommendations = []
        
        if risk_level == 'high':
            recommendations.append('⚠️ IMMEDIATE ATTENTION: User shows multiple high-risk indicators')
            recommendations.append('Consider reaching out with support resources')
        
        if 'crisis_burst' in pattern:
            recommendations.append('Monitor for immediate crisis - user showing burst activity with negative content')
        
        if 'High sentiment volatility' in risk_factors:
            recommendations.append('Track user over time - emotional instability detected')
        
        if 'High cognitive distortion rate' in risk_factors:
            recommendations.append('Content shows significant distorted thinking patterns')
        
        if 'declining_engagement' in pattern:
            recommendations.append('User may be withdrawing - check for prolonged silence periods')
        
        if not recommendations:
            recommendations.append('Continue routine monitoring')
        
        return recommendations


# Global instance
pattern_service = None

def get_pattern_service() -> PatternAnalysisService:
    """Get or create Pattern Analysis service instance"""
    global pattern_service
    if pattern_service is None:
        pattern_service = PatternAnalysisService()
    return pattern_service
