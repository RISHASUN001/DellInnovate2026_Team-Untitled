"""
Analytics Routes for NLP Pipeline and Risk Assessment
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger

from config.database import MongoDB
from analytics.signal_extraction import NLPSignalExtractor, run_nlp_extraction
from analytics.feature_engineering import BehavioralFeatureEngineer, run_feature_engineering
from analytics.llm_integration import LLMSummarizer
from services.case_promotion import promote_risk_profiles_to_scs_cases, CasePromotionService

router = APIRouter()

# ============================================================================
# STAGE 1: NLP Signal Extraction Endpoints
# ============================================================================

@router.post("/extract-signals", response_model=Dict)
async def extract_nlp_signals(
    case_users: Optional[List[str]] = Body(None, description="Specific users to process"),
    limit: Optional[int] = Body(None, description="Maximum posts to process"),
    export_csv: bool = Body(True, description="Export results to CSV"),
    csv_path: str = Body("nlp_signals.csv", description="Path for CSV export")
):
    """
    Stage 1: Extract NLP signals from Instagram posts
    
    Processes posts and comments through:
    - Sentiment Analysis
    - Emotion Detection
    - Cognitive Distortion Detection
    
    Stores results in text_units_signals collection
    """
    try:
        logger.info("Starting NLP signal extraction...")
        extractor = NLPSignalExtractor()
        
        results = await extractor.run_pipeline(
            case_users=case_users,
            limit=limit,
            export_csv=export_csv,
            csv_path=csv_path
        )
        
        return {
            "status": "success",
            "message": "NLP signal extraction completed",
            "results": results
        }
    except Exception as e:
        logger.error(f"Error in NLP extraction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# STAGE 2: Feature Engineering & Risk Scoring Endpoints
# ============================================================================

@router.post("/compute-risk-profiles", response_model=Dict)
async def compute_risk_profiles(
    case_users: Optional[List[str]] = Body(None, description="Specific users to process"),
    window_days: int = Body(7, description="Analysis time window in days")
):
    """
    Stage 2: Compute risk profiles from NLP signals
    
    Aggregates signals and calculates:
    - Distortion metrics
    - Sentiment volatility
    - Distress emotion rates
    - Composite risk scores
    
    Stores results in case_risk_profiles collection
    """
    try:
        logger.info("Starting risk profile computation...")
        engineer = BehavioralFeatureEngineer()
        
        results = await engineer.run_pipeline(
            case_users=case_users,
            window_days=window_days
        )
        
        return {
            "status": "success",
            "message": "Risk profile computation completed",
            "results": results
        }
    except Exception as e:
        logger.error(f"Error computing risk profiles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run-full-pipeline", response_model=Dict)
async def run_full_analytics_pipeline(
    case_users: Optional[List[str]] = Body(None, description="Specific users to process"),
    window_days: int = Body(7, description="Analysis time window in days"),
    limit_posts: Optional[int] = Body(None, description="Maximum posts to process in Stage 1"),
    promote_to_cases: bool = Body(False, description="Promote results to SCS cases"),
    min_priority: str = Body("medium", description="Minimum priority for case promotion")
):
    """
    Run complete analytics pipeline (Stages 1 + 2 + optional promotion)
    
    This endpoint:
    1. Extracts NLP signals from Instagram data
    2. Computes risk profiles
    3. Optionally promotes to SCS cases
    """
    try:
        start_time = datetime.utcnow()
        logger.info("=" * 70)
        logger.info("Starting Full Analytics Pipeline")
        logger.info("=" * 70)
        
        db = MongoDB.get_db()
        
        # Stage 1: NLP Extraction
        logger.info("\n[Stage 1] Extracting NLP signals...")
        extractor = NLPSignalExtractor()
        stage1_results = await extractor.run_pipeline(
            case_users=case_users,
            limit=limit_posts,
            export_csv=False
        )
        
        # Stage 2: Risk Profile Computation
        logger.info("\n[Stage 2] Computing risk profiles...")
        engineer = BehavioralFeatureEngineer()
        stage2_results = await engineer.run_pipeline(
            case_users=case_users,
            window_days=window_days
        )
        
        # Stage 3: Case Promotion (Optional)
        stage3_results = None
        if promote_to_cases:
            logger.info("\n[Stage 3] Promoting to SCS cases...")
            stage3_results = await promote_risk_profiles_to_scs_cases(
                db=db,
                min_priority=min_priority,
                limit=None
            )
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info("=" * 70)
        logger.success(f"Full pipeline completed in {duration:.2f} seconds")
        logger.info("=" * 70)
        
        return {
            "status": "success",
            "message": "Full analytics pipeline completed",
            "started_at": start_time.isoformat(),
            "duration_seconds": duration,
            "results": {
                "stage1_nlp_extraction": stage1_results,
                "stage2_feature_engineering": stage2_results,
                "stage3_case_promotion": stage3_results
            }
        }
        
    except Exception as e:
        logger.error(f"Error in full pipeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Data Query Endpoints
# ============================================================================

@router.get("/risk-profiles", response_model=Dict)
async def get_risk_profiles(
    risk_level: Optional[str] = Query(None, description="Filter by risk level (Low, Medium, High)"),
    min_score: Optional[float] = Query(None, description="Minimum risk score"),
    max_score: Optional[float] = Query(None, description="Maximum risk score"),
    limit: int = Query(50, description="Maximum results")
):
    """
    Get risk profiles with optional filters
    """
    try:
        db = MongoDB.get_db()
        collection = db.case_risk_profiles
        
        # Build query
        query = {}
        if risk_level:
            query["risk_level"] = risk_level
        if min_score is not None or max_score is not None:
            query["risk_score"] = {}
            if min_score is not None:
                query["risk_score"]["$gte"] = min_score
            if max_score is not None:
                query["risk_score"]["$lte"] = max_score
        
        # Get total count
        total = await collection.count_documents(query)
        
        # Get profiles
        cursor = collection.find(query).sort("risk_score", -1).limit(limit)
        profiles = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string
        for profile in profiles:
            profile["_id"] = str(profile["_id"])
        
        return {
            "total": total,
            "returned": len(profiles),
            "profiles": profiles
        }
        
    except Exception as e:
        logger.error(f"Error getting risk profiles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk-profiles/{username}", response_model=Dict)
async def get_user_risk_profile(username: str):
    """
    Get risk profile for a specific user
    """
    try:
        db = MongoDB.get_db()
        collection = db.case_risk_profiles
        
        profile = await collection.find_one({"case_user": username})
        
        if not profile:
            raise HTTPException(status_code=404, detail=f"No risk profile found for user: {username}")
        
        profile["_id"] = str(profile["_id"])
        
        return profile
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user risk profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals", response_model=Dict)
async def get_all_signals(
    case_user: Optional[str] = Query(None, description="Filter by case user"),
    text_type: Optional[str] = Query(None, description="Filter by text type (caption/comment)"),
    limit: int = Query(100, description="Maximum results")
):
    """
    Get NLP signals with optional filters
    """
    try:
        db = MongoDB.get_db()
        collection = db.text_units_signals
        
        # Build query
        query = {}
        if case_user:
            query["case_user"] = case_user
        if text_type:
            query["text_type"] = text_type
        
        # Get total count
        total = await collection.count_documents(query)
        
        # Get signals
        cursor = collection.find(query).sort("processed_at", -1).limit(limit)
        signals = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string
        for signal in signals:
            signal["_id"] = str(signal["_id"])
        
        return {
            "total": total,
            "returned": len(signals),
            "signals": signals
        }
        
    except Exception as e:
        logger.error(f"Error getting signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals/{username}", response_model=Dict)
async def get_user_signals(
    username: str,
    limit: int = Query(100, description="Maximum results")
):
    """
    Get NLP signals for a specific user
    """
    try:
        db = MongoDB.get_db()
        collection = db.text_units_signals
        
        cursor = collection.find({"case_user": username}).sort("processed_at", -1).limit(limit)
        signals = await cursor.to_list(length=limit)
        
        for signal in signals:
            signal["_id"] = str(signal["_id"])
        
        return {
            "case_user": username,
            "total": len(signals),
            "signals": signals
        }
        
    except Exception as e:
        logger.error(f"Error getting user signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=Dict)
async def get_analytics_stats():
    """
    Get overall analytics statistics
    """
    try:
        db = MongoDB.get_db()
        
        # Get counts
        signals_count = await db.text_units_signals.count_documents({})
        profiles_count = await db.case_risk_profiles.count_documents({})
        
        # Get risk level distribution
        pipeline = [
            {"$group": {"_id": "$risk_level", "count": {"$sum": 1}}}
        ]
        cursor = db.case_risk_profiles.aggregate(pipeline)
        risk_distribution = {}
        async for doc in cursor:
            risk_distribution[doc["_id"]] = doc["count"]
        
        # Get average risk score
        avg_pipeline = [
            {"$group": {"_id": None, "avg_score": {"$avg": "$risk_score"}}}
        ]
        cursor = db.case_risk_profiles.aggregate(avg_pipeline)
        avg_result = await cursor.to_list(length=1)
        avg_score = avg_result[0]["avg_score"] if avg_result else 0
        
        return {
            "total_signals": signals_count,
            "total_profiles": profiles_count,
            "risk_distribution": risk_distribution,
            "average_risk_score": avg_score,
            "high_risk_cases": risk_distribution.get("High", 0)
        }
        
    except Exception as e:
        logger.error(f"Error getting analytics stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/cases", response_model=Dict)
async def get_dashboard_cases():
    """
    Get cases formatted for the frontend dashboard
    This is the main endpoint used by the React frontend
    """
    try:
        db = MongoDB.get_db()
        profiles_collection = db.case_risk_profiles
        
        # Get all profiles, sorted by risk score
        cursor = profiles_collection.find().sort("risk_score", -1).limit(50)
        profiles = await cursor.to_list(length=50)
        
        # Transform to dashboard format
        dashboard_cases = []
        
        for idx, profile in enumerate(profiles):
            # Map risk level to category
            risk_level = profile.get("risk_level", "Low")
            if risk_level == "High":
                if profile.get("risk_score", 0) >= 80:
                    category = "Critical"
                else:
                    category = "High Risk"
            elif risk_level == "Medium":
                category = "Moderate Risk"
            else:
                category = "Monitoring"
            
            # Build signals list
            signals = profile.get("key_signals", [])
            if not signals:
                signals = [
                    f"Distress rate: {profile.get('distress_emotion_rate', 0):.1%}",
                    f"Distortion rate: {profile.get('distortion_rate', 0):.1%}",
                    f"Risk score: {profile.get('risk_score', 0):.1f}"
                ]
            
            # Build summary
            distress_rate = profile.get("distress_emotion_rate", 0)
            distortion_rate = profile.get("distortion_rate", 0)
            
            if distress_rate > 0.5:
                summary = f"High distress levels ({distress_rate:.0%} of comments). "
            elif distress_rate > 0.3:
                summary = f"Moderate distress detected ({distress_rate:.0%} of comments). "
            else:
                summary = f"Low distress levels ({distress_rate:.0%} of comments). "
            
            if distortion_rate > 0.3:
                summary += f"Shows patterns of negative thinking ({distortion_rate:.0%} of comments)."
            elif distortion_rate > 0.1:
                summary += f"Occasional negative thinking patterns detected."
            
            # Create dashboard case
            case = {
                'id': idx + 1,
                'case_user': profile.get('case_user', 'unknown'),
                'code': f"YD-{datetime.utcnow().year}-{str(idx+1).zfill(4)}",
                'riskLevel': min(5, max(1, int(profile.get('risk_score', 30) / 20) + 1)),
                'category': category,
                'platform': 'Instagram',
                'lastSignal': profile.get('window_end', datetime.utcnow()).strftime("%Y-%m-%d %I:%M %p"),
                'status': 'Active' if profile.get('risk_level') != 'Low' else 'Monitoring',
                'assignedTo': 'Sarah L.' if idx < 3 else 'Michael T.',
                'assignedToMe': idx < 3,
                'youth': {
                    'name': profile.get('case_user', 'Unknown User'),
                    'age': 15 + (idx % 5),
                    'avatar': ['🧑‍🦱', '👦', '👧', '🧑', '👱'][idx % 5],
                    'handle': f"@{profile.get('case_user', 'user')}",
                    'instagramUrl': f"https://instagram.com/{profile.get('case_user', 'user')}"
                },
                'signals': signals[:5],
                'key_signals': signals[:3],
                'summary': summary,
                'ai_explanation': profile.get('llm_explanation', ''),
                'llm_explanation': profile.get('llm_explanation', ''),
                'llm_category': profile.get('llm_category', ''),
                'llm_recommendations': profile.get('llm_recommendations', []),
                'has_llm_analysis': profile.get('has_llm_analysis', False),
                'nlp_metrics': {
                    'total_signals': profile.get('total_text_units', 0),
                    'distress_count': profile.get('distress_emotion_count', 0),
                    'distortion_count': profile.get('distortion_count', 0),
                    'avg_sentiment': profile.get('avg_sentiment_score', 0),
                    'distress_rate': profile.get('distress_emotion_rate', 0),
                    'emotion_distribution': profile.get('emotion_distribution', {})
                }
            }
            
            dashboard_cases.append(case)
        
        return {
            "status": "success",
            "cases": dashboard_cases
        }
        
    except Exception as e:
        logger.error(f"Error getting dashboard cases: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/case/{case_user}/signals", response_model=Dict)
async def get_case_signals_for_dashboard(
    case_user: str,
    limit: int = Query(50, description="Maximum signals to return")
):
    """
    Get detailed signals for a specific case (for dashboard detail view)
    """
    try:
        db = MongoDB.get_db()
        collection = db.text_units_signals
        
        cursor = collection.find(
            {"case_user": case_user}
        ).sort("processed_at", -1).limit(limit)
        
        signals = await cursor.to_list(length=limit)
        
        # Format for dashboard
        formatted_signals = []
        for signal in signals:
            formatted_signals.append({
                'id': str(signal['_id']),
                'text': signal.get('text', '')[:100],
                'sentiment_label': signal.get('sentiment_label', 'neutral'),
                'sentiment_score': signal.get('sentiment_score', 0),
                'emotion_label': signal.get('emotion_label', 'neutral'),
                'is_distress': signal.get('is_distress', False),
                'distortion_indicator': signal.get('distortion_indicator', 0),
                'text_type': signal.get('text_type', 'unknown'),
                'timestamp': signal.get('processed_at', datetime.utcnow()).isoformat() if signal.get('processed_at') else None
            })
        
        return {
            "case_user": case_user,
            "total": len(formatted_signals),
            "signals": formatted_signals
        }
        
    except Exception as e:
        logger.error(f"Error getting case signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SCS Case Management Endpoints
# ============================================================================

@router.post("/promote-to-cases", response_model=Dict)
async def promote_to_cases(
    min_priority: str = Query("medium", description="Minimum priority to promote (low, medium, high, critical)"),
    limit: Optional[int] = Query(None, description="Maximum number of profiles to process")
):
    """
    Promote risk profiles to operational SCS cases
    
    This creates/updates records in:
    - scs_cases (case records)
    - scs_case_history (historical snapshots)
    - scs_checklist (task items)
    """
    try:
        db = MongoDB.get_db()
        result = await promote_risk_profiles_to_scs_cases(
            db=db,
            min_priority=min_priority,
            limit=limit
        )
        return result
    except Exception as e:
        logger.error(f"Error promoting to cases: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cases/summary", response_model=Dict)
async def get_cases_summary(
    priority: Optional[str] = Query(None, description="Filter by priority level"),
    case_status: Optional[str] = Query(None, description="Filter by case status"),
    work_status: Optional[str] = Query(None, description="Filter by work status"),
    limit: int = Query(50, description="Maximum results")
):
    """
    Get summary of operational cases
    """
    try:
        db = MongoDB.get_db()
        cases_collection = db.scs_cases
        
        # Build query
        query = {}
        if priority:
            query["priority"] = priority
        if case_status:
            query["case_status"] = case_status
        if work_status:
            query["work_status"] = work_status
        
        # Get total counts
        total_cases = await cases_collection.count_documents({})
        filtered_count = await cases_collection.count_documents(query)
        
        # Get cases
        cursor = cases_collection.find(query).sort("current_risk_score", -1).limit(limit)
        cases = await cursor.to_list(length=limit)
        
        # Convert ObjectId to string for JSON
        for case in cases:
            case["_id"] = str(case["_id"])
        
        # Get additional stats
        critical_count = await cases_collection.count_documents({"priority": "critical"})
        unassigned_count = await cases_collection.count_documents({"case_status": "unassigned"})
        
        return {
            "total_cases": total_cases,
            "critical_cases": critical_count,
            "unassigned_cases": unassigned_count,
            "filtered_count": filtered_count,
            "cases": cases
        }
        
    except Exception as e:
        logger.error(f"Error getting cases summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# LLM Explanation Generation Endpoint (CRITICAL - This was missing!)
# ============================================================================

@router.post("/generate-explanation/{username}", response_model=Dict)
async def generate_explanation_for_user(username: str):
    """
    Generate AI explanation on-demand for a specific user
    Call this when a youth worker views a profile
    """
    try:
        db = MongoDB.get_db()
        profiles_collection = db.case_risk_profiles
        
        # Get the profile
        profile = await profiles_collection.find_one({"case_user": username})
        if not profile:
            raise HTTPException(status_code=404, detail=f"User {username} not found")
        
        # Initialize LLM summarizer
        summarizer = LLMSummarizer(use_llm=True)
        
        # Generate explanation
        logger.info(f"Generating explanation for {username}...")
        llm_insights = await summarizer.summarize_risk_profile(profile)
        
        # Update profile with LLM insights
        await profiles_collection.update_one(
            {"case_user": username},
            {"$set": {
                "llm_explanation": llm_insights['explanation'],
                "llm_category": llm_insights['llm_category'],
                "llm_recommendations": llm_insights['recommendations'],
                "llm_generated_at": llm_insights['generated_at'],
                "has_llm_analysis": True,
                "explanation": llm_insights['explanation'],
                "ai_explanation": llm_insights['explanation']
            }}
        )
        
        logger.success(f"Explanation generated for {username}")
        
        return {
            "status": "success",
            "explanation": llm_insights['explanation'],
            "category": llm_insights['llm_category'],
            "recommendations": llm_insights['recommendations']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating explanation: {e}")
        raise HTTPException(status_code=500, detail=str(e))