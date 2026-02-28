"""
Analytics API Routes

Endpoints for running the emotional distress detection pipeline
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from loguru import logger

from analytics.signal_extraction import run_nlp_extraction
from analytics.feature_engineering import run_feature_engineering
from config.database import MongoDB

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


# ========== Request/Response Models ==========

class PipelineRequest(BaseModel):
    """Request model for pipeline execution"""
    case_users: Optional[List[str]] = Field(None, description="Specific users to process (None = all)")
    window_days: Optional[int] = Field(7, description="Time window for feature engineering (days)")
    limit_posts: Optional[int] = Field(None, description="Maximum posts to process in Stage 1")
    

class PipelineResponse(BaseModel):
    """Response model for pipeline execution"""
    status: str
    message: str
    results: dict
    started_at: datetime


class RiskProfileQuery(BaseModel):
    """Query parameters for risk profiles"""
    min_risk_score: Optional[float] = Field(None, description="Minimum risk score filter")
    risk_level: Optional[str] = Field(None, description="Risk level filter (Low/Medium/High)")
    priority: Optional[int] = Field(None, description="Priority level filter (1/2/3)")
    limit: Optional[int] = Field(50, description="Maximum results to return")


# ========== Stage 1: NLP Signal Extraction ==========

@router.post("/extract-signals", response_model=PipelineResponse)
async def extract_nlp_signals(request: PipelineRequest):
    """
    Run Stage 1: NLP Signal Extraction Pipeline
    
    Extracts text units from Instagram posts and runs:
    - Sentiment analysis
    - Emotion detection
    - Cognitive distortion detection
    
    Stores results in text_units_signals collection and exports to CSV.
    """
    try:
        logger.info(f"Starting NLP signal extraction: {request.dict()}")
        started_at = datetime.utcnow()
        
        results = await run_nlp_extraction(
            case_users=request.case_users,
            limit=request.limit_posts
        )
        
        return PipelineResponse(
            status="success",
            message="NLP signal extraction completed",
            results=results,
            started_at=started_at
        )
    
    except Exception as e:
        logger.error(f"NLP extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Stage 2: Feature Engineering ==========

@router.post("/compute-risk-profiles", response_model=PipelineResponse)
async def compute_risk_profiles(request: PipelineRequest):
    """
    Run Stage 2: Behavioral Feature Engineering Pipeline
    
    Aggregates NLP signals and computes:
    - Distortion metrics
    - Sentiment volatility
    - Engagement patterns
    - Risk scores and priorities
    
    Stores results in case_risk_profiles collection.
    """
    try:
        logger.info(f"Starting feature engineering: {request.dict()}")
        started_at = datetime.utcnow()
        
        results = await run_feature_engineering(
            case_users=request.case_users,
            window_days=request.window_days or 7
        )
        
        return PipelineResponse(
            status="success",
            message="Risk profile computation completed",
            results=results,
            started_at=started_at
        )
    
    except Exception as e:
        logger.error(f"Feature engineering failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Full Pipeline ==========

@router.post("/run-full-pipeline", response_model=PipelineResponse)
async def run_full_pipeline(request: PipelineRequest):
    """
    Run Complete Analytics Pipeline (Stage 1 + Stage 2)
    
    Executes both:
    1. NLP signal extraction from Instagram posts
    2. Behavioral feature engineering and risk scoring
    
    This is a comprehensive analysis that may take several minutes.
    """
    try:
        logger.info(f"Starting full analytics pipeline: {request.dict()}")
        started_at = datetime.utcnow()
        
        # Stage 1: Extract signals
        logger.info("Running Stage 1: NLP Signal Extraction...")
        stage1_results = await run_nlp_extraction(
            case_users=request.case_users,
            limit=request.limit_posts
        )
        
        # Stage 2: Compute risk profiles
        logger.info("Running Stage 2: Feature Engineering...")
        stage2_results = await run_feature_engineering(
            case_users=request.case_users,
            window_days=request.window_days or 7
        )
        
        combined_results = {
            'stage1_nlp_extraction': stage1_results,
            'stage2_feature_engineering': stage2_results,
            'total_duration_seconds': (
                stage1_results.get('duration_seconds', 0) +
                stage2_results.get('duration_seconds', 0)
            )
        }
        
        return PipelineResponse(
            status="success",
            message="Full analytics pipeline completed",
            results=combined_results,
            started_at=started_at
        )
    
    except Exception as e:
        logger.error(f"Full pipeline failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Query Risk Profiles ==========

@router.get("/risk-profiles")
async def get_risk_profiles(
    min_risk_score: Optional[float] = None,
    risk_level: Optional[str] = None,
    priority: Optional[int] = None,
    limit: int = 50
):
    """
    Query risk profiles with optional filters
    
    Returns ranked list of case risk profiles for dashboard display.
    """
    try:
        db = MongoDB.get_db()
        profiles_collection = db.case_risk_profiles
        
        # Build query
        query = {}
        if min_risk_score is not None:
            query['risk_score'] = {'$gte': min_risk_score}
        if risk_level:
            query['risk_level'] = risk_level
        if priority is not None:
            query['priority'] = priority
        
        # Fetch profiles sorted by risk score (descending)
        profiles = await profiles_collection.find(query) \
            .sort('risk_score', -1) \
            .limit(limit) \
            .to_list(length=None)
        
        # Convert ObjectId to string
        for profile in profiles:
            if '_id' in profile:
                profile['_id'] = str(profile['_id'])
        
        return {
            'count': len(profiles),
            'profiles': profiles
        }
    
    except Exception as e:
        logger.error(f"Error querying risk profiles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk-profiles/{username}")
async def get_risk_profile_by_username(username: str):
    """
    Get risk profile for a specific case user
    """
    try:
        db = MongoDB.get_db()
        profiles_collection = db.case_risk_profiles
        
        profile = await profiles_collection.find_one({'case_user': username})
        
        if not profile:
            raise HTTPException(status_code=404, detail=f"No risk profile found for {username}")
        
        # Convert ObjectId to string
        if '_id' in profile:
            profile['_id'] = str(profile['_id'])
        
        return profile
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching risk profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Query Signals ==========

@router.get("/signals")
async def get_all_signals(
    limit: int = 500,
    distress_only: bool = False,
    case_user: Optional[str] = None
):
    """
    Get all NLP signals from the database
    
    Returns all text units with complete sentiment, emotion, and distortion analysis.
    This endpoint provides all columns produced by the NLP pipeline.
    """
    try:
        db = MongoDB.get_db()
        signals_collection = db.text_units_signals
        
        # Build query
        query = {}
        if case_user:
            query['case_user'] = case_user
        if distress_only:
            query['is_distress'] = True
        
        signals = await signals_collection.find(query) \
            .sort('processed_at', -1) \
            .limit(limit) \
            .to_list(length=None)
        
        # Convert ObjectId to string and datetime to ISO format
        for signal in signals:
            if '_id' in signal:
                signal['_id'] = str(signal['_id'])
            if 'processed_at' in signal and signal['processed_at']:
                signal['processed_at'] = signal['processed_at'].isoformat()
            if 'timestamp' in signal and signal['timestamp']:
                signal['timestamp'] = signal['timestamp'].isoformat() if hasattr(signal['timestamp'], 'isoformat') else str(signal['timestamp'])
        
        return {
            'count': len(signals),
            'signals': signals
        }
    
    except Exception as e:
        logger.error(f"Error fetching all signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals/{username}")
async def get_signals_for_user(
    username: str,
    limit: int = 100,
    distress_only: bool = False
):
    """
    Get NLP signals for a specific user
    
    Returns text units with sentiment, emotion, and distortion analysis.
    """
    try:
        db = MongoDB.get_db()
        signals_collection = db.text_units_signals
        
        # Build query
        query = {'case_user': username}
        if distress_only:
            query['is_distress'] = True
        
        signals = await signals_collection.find(query) \
            .sort('processed_at', -1) \
            .limit(limit) \
            .to_list(length=None)
        
        # Convert ObjectId to string and datetime to ISO format
        for signal in signals:
            if '_id' in signal:
                signal['_id'] = str(signal['_id'])
            if 'processed_at' in signal and signal['processed_at']:
                signal['processed_at'] = signal['processed_at'].isoformat()
            if 'timestamp' in signal and signal['timestamp']:
                signal['timestamp'] = signal['timestamp'].isoformat() if hasattr(signal['timestamp'], 'isoformat') else str(signal['timestamp'])
        
        return {
            'count': len(signals),
            'case_user': username,
            'signals': signals
        }
    
    except Exception as e:
        logger.error(f"Error fetching signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Statistics ==========

@router.get("/stats")
async def get_analytics_stats():
    """
    Get overall analytics statistics
    """
    try:
        db = MongoDB.get_db()
        
        # Count signals
        signals_count = await db.text_units_signals.count_documents({})
        
        # Count profiles
        profiles_count = await db.case_risk_profiles.count_documents({})
        
        # High-risk count
        high_risk_count = await db.case_risk_profiles.count_documents({'risk_level': 'High'})
        
        # Average risk score
        pipeline = [
            {'$group': {
                '_id': None,
                'avg_risk_score': {'$avg': '$risk_score'},
                'max_risk_score': {'$max': '$risk_score'}
            }}
        ]
        risk_stats = await db.case_risk_profiles.aggregate(pipeline).to_list(length=1)
        
        avg_risk = risk_stats[0]['avg_risk_score'] if risk_stats else 0
        max_risk = risk_stats[0]['max_risk_score'] if risk_stats else 0
        
        return {
            'total_signals': signals_count,
            'total_profiles': profiles_count,
            'high_risk_cases': high_risk_count,
            'average_risk_score': round(avg_risk, 2),
            'max_risk_score': round(max_risk, 2)
        }
    
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Dashboard Data ==========

@router.get("/dashboard/cases")
async def get_dashboard_cases(limit: int = 100):
    """
    Get cases for dashboard display with aggregated NLP data
    
    Aggregates signals per case user and returns dashboard-ready case objects
    with risk levels, categories, and signal summaries.
    """
    try:
        db = MongoDB.get_db()
        signals_collection = db.text_units_signals
        profiles_collection = db.case_risk_profiles
        users_collection = db.instagram_users
        
        # Get all unique case users from signals
        case_users = await signals_collection.distinct('case_user')
        
        cases = []
        for idx, case_user in enumerate(case_users[:limit]):
            # Get signals for this user
            signals = await signals_collection.find({'case_user': case_user}) \
                .sort('processed_at', -1) \
                .limit(50) \
                .to_list(length=None)
            
            if not signals:
                continue
            
            # Get risk profile if exists
            risk_profile = await profiles_collection.find_one({'case_user': case_user})
            
            # Get user info if exists
            user_info = await users_collection.find_one({'username': case_user})
            
            # Calculate aggregated metrics
            total_signals = len(signals)
            distress_count = sum(1 for s in signals if s.get('is_distress', False))
            distortion_count = sum(1 for s in signals if s.get('distortion_indicator', 0) == 1)
            avg_sentiment = sum(s.get('sentiment_score', 0) for s in signals) / total_signals if total_signals > 0 else 0
            
            # Calculate rates upfront
            distress_rate = distress_count / total_signals if total_signals > 0 else 0
            distortion_rate = distortion_count / total_signals if total_signals > 0 else 0
            
            # Get emotion distribution
            emotion_counts = {}
            for s in signals:
                emotion = s.get('emotion_label', 'neutral')
                emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
            
            # Determine risk level (1-5)
            risk_level = 1
            if risk_profile:
                risk_score = risk_profile.get('risk_score', 0)
                if risk_score >= 0.8:
                    risk_level = 5
                elif risk_score >= 0.6:
                    risk_level = 4
                elif risk_score >= 0.4:
                    risk_level = 3
                elif risk_score >= 0.2:
                    risk_level = 2
            else:
                # Estimate risk level from signals
                if distress_rate >= 0.5 or distortion_rate >= 0.3:
                    risk_level = 5
                elif distress_rate >= 0.3 or distortion_rate >= 0.2:
                    risk_level = 4
                elif distress_rate >= 0.2 or distortion_rate >= 0.1:
                    risk_level = 3
                elif distress_rate >= 0.1:
                    risk_level = 2
            
            # Determine category based on signals
            dominant_emotion = max(emotion_counts, key=emotion_counts.get) if emotion_counts else 'neutral'
            category_map = {
                'sadness': 'Loneliness / Isolation',
                'fear': 'Self-Harm Ideation',
                'anger': 'Bullying',
                'disgust': 'Cyberbullying',
                'surprise': 'Academic Stress',
                'joy': 'Monitoring',
                'neutral': 'Monitoring'
            }
            category = category_map.get(dominant_emotion, 'Monitoring')
            
            # If high distortion, might indicate bullying
            if distortion_count > 0:
                category = 'Bullying'
            
            # Get most recent signal time
            last_signal_time = signals[0].get('processed_at', datetime.utcnow())
            if hasattr(last_signal_time, 'strftime'):
                last_signal = last_signal_time.strftime('%Y-%m-%d %I:%M %p')
            else:
                last_signal = str(last_signal_time)
            
            # Generate AI signals (explanations)
            ai_signals = []
            if distress_count > 0:
                ai_signals.append(f"Distress indicators detected in {distress_count} of {total_signals} text units")
            if distortion_count > 0:
                ai_signals.append(f"Cognitive distortion patterns found in {distortion_count} comments")
            if avg_sentiment < -0.3:
                ai_signals.append(f"Negative sentiment trend detected (avg: {avg_sentiment:.2f})")
            if emotion_counts.get('sadness', 0) > total_signals * 0.3:
                ai_signals.append("High frequency of sadness indicators")
            if emotion_counts.get('fear', 0) > total_signals * 0.2:
                ai_signals.append("Fear-related language patterns identified")
            if not ai_signals:
                ai_signals.append("Regular monitoring - no significant distress signals")
            
            # Generate summary
            summary = f"Analysis of {total_signals} text units. "
            if distress_rate > 0.2:
                summary += f"Elevated distress signals ({distress_rate*100:.0f}% of content). "
            if avg_sentiment < -0.2:
                summary += f"Generally negative sentiment detected. "
            elif avg_sentiment > 0.5:
                summary += f"Positive sentiment overall. "
            summary += f"Primary emotion: {dominant_emotion}."
            
            # Determine status
            status = "Monitoring"
            if risk_level >= 4:
                status = "Active"
            if risk_level == 5:
                status = "Escalated"
            
            case = {
                'id': idx + 1,
                'code': f"YD-2026-{1000 + idx:04d}",
                'riskLevel': risk_level,
                'category': category,
                'platform': 'Instagram',
                'lastSignal': last_signal,
                'status': status,
                'assignedTo': '—',
                'assignedToMe': False,
                'youth': {
                    'name': user_info.get('name', case_user) if user_info else case_user,
                    'age': 15,  # Default since we don't have age data
                    'avatar': '👤',
                    'handle': f'@{case_user}',
                    'instagramUrl': f'https://instagram.com/{case_user}'
                },
                'signals': ai_signals[:3],
                'summary': summary,
                'case_user': case_user,
                # NLP metrics
                'nlp_metrics': {
                    'total_signals': total_signals,
                    'distress_count': distress_count,
                    'distortion_count': distortion_count,
                    'avg_sentiment': round(avg_sentiment, 3),
                    'emotion_distribution': emotion_counts,
                    'distress_rate': round(distress_count / total_signals, 3) if total_signals > 0 else 0,
                    'distortion_rate': round(distortion_count / total_signals, 3) if total_signals > 0 else 0
                }
            }
            
            cases.append(case)
        
        # Sort by risk level descending
        cases.sort(key=lambda x: x['riskLevel'], reverse=True)
        
        return {
            'count': len(cases),
            'cases': cases
        }
    
    except Exception as e:
        logger.error(f"Error fetching dashboard cases: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/case/{case_user}/signals")
async def get_case_signals_detail(case_user: str, limit: int = 100):
    """
    Get detailed NLP signals for a specific case user
    
    Returns all signal columns for display in the frontend.
    """
    try:
        db = MongoDB.get_db()
        signals_collection = db.text_units_signals
        
        signals = await signals_collection.find({'case_user': case_user}) \
            .sort('processed_at', -1) \
            .limit(limit) \
            .to_list(length=None)
        
        # Convert for JSON serialization
        formatted_signals = []
        for signal in signals:
            formatted_signal = {
                'id': str(signal.get('_id', '')),
                'case_user': signal.get('case_user', ''),
                'text_type': signal.get('text_type', ''),
                'text': signal.get('text', ''),
                'post_id': signal.get('post_id', ''),
                'comment_id': signal.get('comment_id'),
                'author': signal.get('author'),
                'timestamp': signal.get('timestamp').isoformat() if signal.get('timestamp') and hasattr(signal.get('timestamp'), 'isoformat') else str(signal.get('timestamp', '')),
                
                # Sentiment analysis
                'sentiment_label': signal.get('sentiment_label', 'neutral'),
                'sentiment_score': signal.get('sentiment_score', 0),
                'sentiment_probabilities': signal.get('sentiment_probabilities', {}),
                
                # Emotion analysis
                'emotion_label': signal.get('emotion_label', 'neutral'),
                'emotion_score': signal.get('emotion_score', 0),
                'emotion_probabilities': signal.get('emotion_probabilities', {}),
                'is_distress': signal.get('is_distress', False),
                'distress_score': signal.get('distress_score', 0),
                
                # Distortion analysis
                'distortion_indicator': signal.get('distortion_indicator', 0),
                'distortion_score': signal.get('distortion_score', 0),
                'distortion_category': signal.get('distortion_category'),
                'distortion_all_scores': signal.get('distortion_all_scores', {}),
                
                # Metadata
                'processed_at': signal.get('processed_at').isoformat() if signal.get('processed_at') and hasattr(signal.get('processed_at'), 'isoformat') else str(signal.get('processed_at', '')),
                'preprocessed_text': signal.get('preprocessed_text', ''),
                'language': signal.get('language', '')
            }
            formatted_signals.append(formatted_signal)
        
        return {
            'count': len(formatted_signals),
            'case_user': case_user,
            'signals': formatted_signals
        }
    
    except Exception as e:
        logger.error(f"Error fetching case signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))
