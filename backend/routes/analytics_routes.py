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
        
        # Convert ObjectId to string
        for signal in signals:
            if '_id' in signal:
                signal['_id'] = str(signal['_id'])
        
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
