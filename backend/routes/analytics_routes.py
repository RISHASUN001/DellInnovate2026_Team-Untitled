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
from analytics.stage2_pca_llm import run_case_scoring
from services.case_promotion import promote_risk_profiles_to_scs_cases
from config.database import MongoDB

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


# ========== Request/Response Models ==========

class PipelineRequest(BaseModel):
    """Request model for pipeline execution"""
    case_users: Optional[List[str]] = Field(None, description="Specific users to process (None = all)")
    window_days: Optional[int] = Field(7, description="Time window for feature engineering (days)")
    limit_posts: Optional[int] = Field(None, description="Maximum posts to process in Stage 1")
    use_pca: Optional[bool] = Field(False, description="Use PCA-based scoring instead of legacy")
    use_llm: Optional[bool] = Field(True, description="Use LLM calibration (PCA mode only)")
    llm_model: Optional[str] = Field("llama2", description="Ollama model name (PCA mode only)")
    ollama_url: Optional[str] = Field("http://localhost:11434", description="Ollama endpoint (PCA mode only)")
    

class PCAScoringRequest(BaseModel):
    """Request model for PCA-based scoring pipeline"""
    window_days: Optional[int] = Field(30, description="Time window for signal aggregation (days)")
    limit_users: Optional[int] = Field(None, description="Limit number of users (for testing)")
    use_llm: Optional[bool] = Field(True, description="Whether to use LLM calibration")
    llm_model: Optional[str] = Field("llama2", description="Ollama model name")
    ollama_url: Optional[str] = Field("http://localhost:11434", description="Ollama API endpoint")


class CasePromotionRequest(BaseModel):
    """Request model for promoting risk profiles to SCS cases"""
    min_priority: Optional[str] = Field("medium", description="Minimum priority level ('low', 'medium', 'high', 'critical')")
    limit: Optional[int] = Field(None, description="Limit number of profiles to process (for testing)")
    auto_promotion: Optional[bool] = Field(True, description="Whether to auto-promote after analytics run")


class FullPipelineRequest(BaseModel):
    """Request model for full end-to-end pipeline"""
    case_users: Optional[List[str]] = Field(None, description="Specific users to process (None = all)")
    window_days: Optional[int] = Field(30, description="Time window for aggregation (days)")
    use_llm: Optional[bool] = Field(True, description="Use LLM calibration in scoring")
    llm_model: Optional[str] = Field("llama2", description="Ollama model name")
    min_priority: Optional[str] = Field("medium", description="Minimum priority for case creation")
    promote_to_cases: Optional[bool] = Field(True, description="Promote results to SCS operational tables")


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
    Run Stage 2: Behavioral Feature Engineering Pipeline (LEGACY)
    
    Aggregates NLP signals and computes:
    - Distortion metrics
    - Sentiment volatility
    - Engagement patterns
    - Risk scores and priorities
    
    Stores results in case_risk_profiles collection.
    
    NOTE: This is the legacy hand-coded feature engineering.
    Consider using /compute-risk-profiles-pca for PCA-based scoring.
    """
    try:
        logger.info(f"Starting feature engineering (legacy): {request.dict()}")
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


@router.post("/compute-risk-profiles-pca", response_model=PipelineResponse)
async def compute_risk_profiles_pca(request: PCAScoringRequest):
    """
    Run Stage 2: PCA-based Risk Profiling with LLM Calibration (NEW)
    
    Computes risk profiles using:
    1. Mean + p90 aggregation for emotion/sentiment/harm scores
    2. Low-data damping (sigmoid function)
    3. PCA weight learning across users
    4. Guardrail to prevent harm_score underweighting
    5. LLM calibration with bounded delta (±0.10)
    
    Produces final_score (0-1) with priority levels: low, medium, high, critical.
    
    Stores results in case_risk_profiles collection with PCA fields.
    """
    try:
        logger.info(f"Starting PCA-based scoring: {request.dict()}")
        started_at = datetime.utcnow()
        
        db = MongoDB.get_db()
        
        results = await run_case_scoring(
            db=db,
            window_days=request.window_days or 30,
            limit_users=request.limit_users,
            use_llm=request.use_llm if request.use_llm is not None else True,
            llm_model=request.llm_model or "llama2",
            ollama_url=request.ollama_url or "http://localhost:11434"
        )
        
        return PipelineResponse(
            status="success" if results['success'] else "failed",
            message=results.get('message', 'PCA-based risk profiling completed'),
            results=results,
            started_at=started_at
        )
    
    except Exception as e:
        logger.error(f"PCA scoring failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Full Pipeline ==========

@router.post("/run-full-pipeline", response_model=PipelineResponse)
async def run_full_pipeline(request: PipelineRequest):
    """
    Run Complete Analytics Pipeline (Stage 1 + Stage 2)
    
    Executes both:
    1. NLP signal extraction from Instagram posts
    2. Behavioral feature engineering and risk scoring
       - Legacy: Hand-coded weights (use_pca=False)
       - PCA: Learned weights + LLM calibration (use_pca=True)
    
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
        if request.use_pca:
            logger.info("Running Stage 2: PCA-based Risk Profiling...")
            db = MongoDB.get_db()
            stage2_results = await run_case_scoring(
                db=db,
                window_days=request.window_days or 30,
                limit_users=None,
                use_llm=request.use_llm if request.use_llm is not None else True,
                llm_model=request.llm_model or "llama2",
                ollama_url=request.ollama_url or "http://localhost:11434"
            )
        else:
            logger.info("Running Stage 2: Feature Engineering (legacy)...")
            stage2_results = await run_feature_engineering(
                case_users=request.case_users,
                window_days=request.window_days or 7
            )
        
        combined_results = {
            'stage1_nlp_extraction': stage1_results,
            'stage2_feature_engineering': stage2_results,
            'scoring_method': 'pca' if request.use_pca else 'legacy',
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
    priority_level: Optional[str] = None,
    limit: int = 50
):
    """
    Query risk profiles with optional filters
    
    Returns ranked list of case risk profiles for dashboard display.
    Supports both legacy (risk_score, risk_level, priority) and 
    PCA-based (final_score, priority_level) fields.
    """
    try:
        db = MongoDB.get_db()
        profiles_collection = db.case_risk_profiles
        
        # Build query
        query = {}
        if min_risk_score is not None:
            # Try both legacy and new fields
            query['$or'] = [
                {'risk_score': {'$gte': min_risk_score}},
                {'final_score': {'$gte': min_risk_score / 100.0}}  # Convert if needed
            ]
        if risk_level:
            query['risk_level'] = risk_level
        if priority is not None:
            query['priority'] = priority
        if priority_level:
            query['priority_level'] = priority_level
        
        # Fetch profiles sorted by final_score (if available) or risk_score
        profiles = await profiles_collection.find(query) \
            .sort([('final_score', -1), ('risk_score', -1)]) \
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


# ========== Case Promotion Endpoints ==========

@router.post("/promote-to-cases", response_model=PipelineResponse)
async def promote_profiles_to_cases(request: CasePromotionRequest):
    """
    Promote risk profiles to operational SCS case management tables.
    
    Takes aggregated risk profiles from case_risk_profiles and:
    1. Creates or updates records in scs_cases
    2. Appends history entries to scs_case_history
    3. Creates mandatory checklist items for new cases (from templates)
    
    This bridges the analytics layer to the operational case management layer.
    
    Priority filtering:
    - 'low': Create cases for all risk levels
    - 'medium': Create cases for medium, high, and critical
    - 'high': Create cases for high and critical only
    - 'critical': Create cases for critical only
    """
    try:
        logger.info(f"Starting case promotion: {request.dict()}")
        started_at = datetime.utcnow()
        
        db = MongoDB.get_db()
        
        results = await promote_risk_profiles_to_scs_cases(
            db=db,
            min_priority=request.min_priority,
            limit=request.limit,
            ingestion_timestamp=started_at
        )
        
        return PipelineResponse(
            status="success",
            message=f"Promoted {results['cases_created']} new cases, updated {results['cases_updated']} existing cases",
            results=results,
            started_at=started_at
        )
    
    except Exception as e:
        logger.error(f"Case promotion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run-full-pipeline", response_model=PipelineResponse)
async def run_full_pipeline(request: FullPipelineRequest):
    """
    Run complete end-to-end pipeline:
    1. Extract NLP signals from Instagram data
    2. Compute risk profiles using PCA + LLM scoring
    3. Promote risk profiles to operational SCS case tables
    
    This is the main endpoint for scheduled ingestion cycles (e.g., every 6 hours).
    
    Returns comprehensive statistics from all stages.
    """
    try:
        logger.info(f"Starting full pipeline: {request.dict()}")
        started_at = datetime.utcnow()
        
        db = MongoDB.get_db()
        
        all_results = {
            "stage1_nlp": None,
            "stage2_scoring": None,
            "stage3_promotion": None
        }
        
        # Stage 1: NLP Signal Extraction
        logger.info("Stage 1: Extracting NLP signals...")
        stage1_results = await run_nlp_extraction(
            case_users=request.case_users,
            limit=None
        )
        all_results["stage1_nlp"] = stage1_results
        logger.info(f"Stage 1 complete: {stage1_results.get('text_units_processed', 0)} units processed")
        
        # Stage 2: PCA + LLM Risk Scoring
        logger.info("Stage 2: Computing risk profiles...")
        stage2_results = await run_case_scoring(
            db=db,
            window_days=request.window_days,
            limit_users=None,
            use_llm=request.use_llm,
            llm_model=request.llm_model
        )
        all_results["stage2_scoring"] = stage2_results
        logger.info(f"Stage 2 complete: {stage2_results.get('profiles_computed', 0)} profiles computed")
        
        # Stage 3: Promote to SCS Cases (if enabled)
        if request.promote_to_cases:
            logger.info("Stage 3: Promoting to SCS cases...")
            stage3_results = await promote_risk_profiles_to_scs_cases(
                db=db,
                min_priority=request.min_priority,
                limit=None,
                ingestion_timestamp=started_at
            )
            all_results["stage3_promotion"] = stage3_results
            logger.info(f"Stage 3 complete: {stage3_results['cases_created']} created, {stage3_results['cases_updated']} updated")
        else:
            logger.info("Stage 3: Skipped (promote_to_cases=False)")
        
        # Calculate total duration
        duration = (datetime.utcnow() - started_at).total_seconds()
        
        return PipelineResponse(
            status="success",
            message=f"Full pipeline completed in {duration:.1f}s",
            results={
                **all_results,
                "duration_seconds": duration,
                "pipeline_version": "v1.0-pca-llm"
            },
            started_at=started_at
        )
    
    except Exception as e:
        logger.error(f"Full pipeline failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cases/summary")
async def get_scs_cases_summary(
    priority: Optional[str] = None,
    case_status: Optional[str] = None,
    limit: int = 50
):
    """
    Get summary of operational SCS cases.
    
    Query parameters:
    - priority: Filter by priority level
    - case_status: Filter by case status
    - limit: Maximum results to return
    """
    try:
        db = MongoDB.get_db()
        
        # Build query filter
        query_filter = {}
        if priority:
            query_filter["priority"] = priority.lower()
        if case_status:
            query_filter["case_status"] = case_status.lower()
        
        # Get cases
        cases = await db.scs_cases.find(query_filter) \
            .sort("priority", 1) \
            .sort("current_risk_score", -1) \
            .limit(limit) \
            .to_list(length=None)
        
        # Convert ObjectId to string
        for case in cases:
            if '_id' in case:
                del case['_id']
        
        # Get statistics
        total_cases = await db.scs_cases.count_documents({})
        critical_cases = await db.scs_cases.count_documents({"priority": "critical"})
        unassigned_cases = await db.scs_cases.count_documents({"case_status": "unassigned"})
        
        return {
            "total_cases": total_cases,
            "critical_cases": critical_cases,
            "unassigned_cases": unassigned_cases,
            "filtered_count": len(cases),
            "cases": cases
        }
    
    except Exception as e:
        logger.error(f"Error fetching SCS cases: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cases/{case_id}/history")
async def get_case_history(case_id: str):
    """
    Get risk score history for a specific case.
    Shows how risk has evolved over time through multiple ingestion cycles.
    """
    try:
        db = MongoDB.get_db()
        
        # Get case info
        case = await db.scs_cases.find_one({"case_id": case_id})
        if not case:
            raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
        
        # Get history entries
        history = await db.scs_case_history.find({"case_id": case_id}) \
            .sort("ingestion_date", 1) \
            .to_list(length=None)
        
        # Clean up
        if '_id' in case:
            del case['_id']
        
        for entry in history:
            if '_id' in entry:
                del entry['_id']
        
        return {
            "case": case,
            "history_count": len(history),
            "history": history
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching case history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
