# routes/analytics_routes.py

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from loguru import logger

from analytics.signal_extraction import run_nlp_extraction
from analytics.feature_engineering import run_feature_engineering
from analytics.llm_summary import LLMSummaryGenerator, generate_llm_summaries
from config.database import MongoDB

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


# ========== Stage 1: NLP Signal Extraction ==========

@router.post("/extract-signals")
async def extract_signals(
    case_users: Optional[List[str]] = Query(None),
    limit: Optional[int] = Query(None)
):
    """
    Stage 1: Extract NLP signals from Instagram posts
    
    Extracts text units and runs sentiment, emotion, and cognitive distortion analysis.
    Stores results in text_units_signals collection.
    """
    try:
        logger.info(f"Starting NLP signal extraction for users: {case_users}")
        result = await run_nlp_extraction(case_users=case_users, limit=limit)
        return {
            "status": "success",
            "message": "NLP signal extraction completed",
            "results": result,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error in signal extraction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Stage 2: Feature Engineering ==========

@router.post("/compute-risk-profiles")
async def compute_risk_profiles(
    case_users: Optional[List[str]] = Query(None),
    window_days: int = 7
):
    """
    Stage 2: Compute risk profiles from signals
    
    Aggregates NLP signals and computes risk scores, distortion metrics,
    sentiment volatility, and engagement patterns.
    Stores results in case_risk_profiles collection.
    """
    try:
        logger.info(f"Starting risk profile computation for users: {case_users}")
        result = await run_feature_engineering(
            case_users=case_users, 
            window_days=window_days
        )
        return {
            "status": "success",
            "message": "Risk profile computation completed",
            "results": result,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error in risk profile computation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Stage 3: LLM Summary Generation ==========

@router.post("/generate-llm-summaries")
async def generate_summaries(
    background_tasks: BackgroundTasks,
    limit: int = Query(5, description="Maximum number of summaries to generate"),
    priority: Optional[int] = Query(None, description="Filter by priority (1=High, 2=Medium, 3=Low)")
):
    """
    Stage 3: Generate LLM summaries for high-risk cases
    
    Uses OpenRouter API to generate comprehensive, empathetic summaries
    for cases with the highest priority. Runs in background to avoid timeouts.
    """
    try:
        logger.info(f"Starting LLM summary generation for up to {limit} cases")
        
        # Run in background to avoid timeout
        background_tasks.add_task(generate_llm_summaries, limit=limit, priority=priority)
        
        return {
            "status": "started",
            "message": f"LLM summary generation started for up to {limit} cases",
            "priority_filter": priority,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error starting LLM summary generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-summary/{username}")
async def generate_summary_for_user(
    background_tasks: BackgroundTasks,
    username: str
):
    """
    Generate LLM summary for a specific user
    
    Creates a comprehensive summary for an individual case user.
    Useful for on-demand summary generation.
    """
    try:
        logger.info(f"Starting LLM summary generation for user: {username}")
        
        async def generate_single():
            generator = LLMSummaryGenerator()
            await generator.generate_summary(username)
        
        background_tasks.add_task(generate_single)
        
        return {
            "status": "started",
            "message": f"LLM summary generation started for {username}",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error starting summary generation for {username}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Full Pipeline ==========

@router.post("/run-full-pipeline")
async def run_full_pipeline(
    background_tasks: BackgroundTasks,
    case_users: Optional[List[str]] = Query(None),
    limit: Optional[int] = Query(None),
    window_days: int = 7,
    generate_summaries: bool = True
):
    """
    Run complete analytics pipeline (Stages 1, 2, and optional Stage 3)
    
    Executes:
    1. NLP signal extraction from Instagram posts
    2. Behavioral feature engineering and risk scoring
    3. (Optional) LLM summary generation for high-risk cases
    
    This comprehensive analysis may take several minutes and runs in the background.
    """
    try:
        logger.info(f"Starting full analytics pipeline for users: {case_users}")
        
        async def pipeline():
            try:
                # Stage 1: Extract signals
                logger.info("Stage 1: Extracting signals...")
                stage1 = await run_nlp_extraction(case_users=case_users, limit=limit)
                
                # Stage 2: Compute risk profiles
                logger.info("Stage 2: Computing risk profiles...")
                stage2 = await run_feature_engineering(
                    case_users=case_users, 
                    window_days=window_days
                )
                
                # Stage 3: Generate LLM summaries
                stage3 = {"generated": [], "failed": [], "skipped": []}
                if generate_summaries and stage2.get('high_risk_cases'):
                    logger.info(f"Stage 3: Generating LLM summaries for {len(stage2.get('high_risk_cases', []))} high-risk cases...")
                    generator = LLMSummaryGenerator()
                    stage3 = await generator.generate_summaries_for_high_risk(limit=10)
                
                logger.success("Full analytics pipeline completed successfully")
                
                # Optionally store pipeline results
                try:
                    db = MongoDB.get_db()
                    await db.pipeline_runs.insert_one({
                        "timestamp": datetime.utcnow(),
                        "case_users": case_users,
                        "stage1": stage1,
                        "stage2": stage2,
                        "stage3": stage3
                    })
                except:
                    pass  # Non-critical, don't fail if storage fails
                
            except Exception as e:
                logger.error(f"Pipeline execution failed: {e}")
        
        # Run in background
        background_tasks.add_task(pipeline)
        
        return {
            "status": "started",
            "message": "Full analytics pipeline started in background",
            "details": {
                "case_users": case_users,
                "window_days": window_days,
                "generate_summaries": generate_summaries
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error starting full pipeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Query Risk Profiles ==========

@router.get("/risk-profiles")
async def get_risk_profiles(
    risk_level: Optional[str] = Query(None, regex="^(High|Medium|Low)$"),
    priority: Optional[int] = Query(None, ge=1, le=3),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get all risk profiles with optional filtering
    
    Returns ranked list of case risk profiles for dashboard display.
    Can filter by risk level (High/Medium/Low) or priority (1-3).
    """
    try:
        db = MongoDB.get_db()
        query = {}
        
        if risk_level:
            query['risk_level'] = risk_level
        if priority:
            query['priority'] = priority
        
        profiles = await db.case_risk_profiles.find(
            query
        ).sort([
            ('priority', 1),
            ('risk_score', -1)
        ]).limit(limit).to_list(length=limit)
        
        # Convert ObjectId to string for JSON serialization
        for profile in profiles:
            profile['_id'] = str(profile['_id'])
        
        return {
            "count": len(profiles),
            "profiles": profiles
        }
        
    except Exception as e:
        logger.error(f"Error fetching risk profiles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk-profiles/{username}")
async def get_risk_profile(username: str):
    """
    Get risk profile for a specific user
    
    Returns complete risk profile with optional LLM summary if available.
    """
    try:
        db = MongoDB.get_db()
        profile = await db.case_risk_profiles.find_one({"case_user": username})
        
        if not profile:
            raise HTTPException(status_code=404, detail="Risk profile not found")
        
        # Get LLM summary if available
        summary = await db.case_llm_summaries.find_one(
            {"case_user": username},
            sort=[("generated_at", -1)]
        )
        
        # Convert ObjectId to string
        profile['_id'] = str(profile['_id'])
        
        if summary:
            summary['_id'] = str(summary['_id'])
            # Format summary for better display
            if 'generated_at' in summary:
                summary['generated_at'] = summary['generated_at'].isoformat()
            profile['llm_summary'] = summary
        
        return profile
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching risk profile for {username}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Query LLM Summaries ==========

@router.get("/llm-summaries")
async def get_llm_summaries(
    username: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50)
):
    """
    Get LLM summaries with optional filtering
    
    Returns generated summaries with metadata.
    """
    try:
        db = MongoDB.get_db()
        query = {}
        
        if username:
            query['case_user'] = username
        
        summaries = await db.case_llm_summaries.find(
            query
        ).sort("generated_at", -1).limit(limit).to_list(length=limit)
        
        # Format for JSON response
        for summary in summaries:
            summary['_id'] = str(summary['_id'])
            if 'generated_at' in summary:
                summary['generated_at'] = summary['generated_at'].isoformat()
        
        return {
            "count": len(summaries),
            "summaries": summaries
        }
        
    except Exception as e:
        logger.error(f"Error fetching LLM summaries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/llm-summaries/{username}")
async def get_user_llm_summaries(
    username: str,
    limit: int = Query(5, ge=1, le=10)
):
    """
    Get LLM summary history for a specific user
    
    Returns all summaries generated for a user, sorted by date.
    """
    try:
        db = MongoDB.get_db()
        
        summaries = await db.case_llm_summaries.find(
            {"case_user": username}
        ).sort("generated_at", -1).limit(limit).to_list(length=limit)
        
        if not summaries:
            return {
                "count": 0,
                "summaries": [],
                "message": "No LLM summaries found for this user"
            }
        
        # Format for JSON response
        for summary in summaries:
            summary['_id'] = str(summary['_id'])
            if 'generated_at' in summary:
                summary['generated_at'] = summary['generated_at'].isoformat()
        
        return {
            "count": len(summaries),
            "case_user": username,
            "summaries": summaries
        }
        
    except Exception as e:
        logger.error(f"Error fetching LLM summaries for {username}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Query Signals ==========

@router.get("/signals")
async def get_all_signals(
    case_user: Optional[str] = Query(None),
    distress_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=500)
):
    """
    Get all signals with optional filtering
    
    Returns text units with complete sentiment, emotion, and distortion analysis.
    """
    try:
        db = MongoDB.get_db()
        query = {}
        
        if case_user:
            query['case_user'] = case_user
        if distress_only:
            query['is_distress'] = True
        
        signals = await db.text_units_signals.find(
            query
        ).sort("processed_at", -1).limit(limit).to_list(length=limit)
        
        # Format for JSON response
        for signal in signals:
            signal['_id'] = str(signal['_id'])
            if 'processed_at' in signal and signal['processed_at']:
                signal['processed_at'] = signal['processed_at'].isoformat()
            if 'timestamp' in signal and signal['timestamp']:
                signal['timestamp'] = signal['timestamp'].isoformat() if hasattr(signal['timestamp'], 'isoformat') else str(signal['timestamp'])
        
        return {
            "count": len(signals),
            "signals": signals
        }
        
    except Exception as e:
        logger.error(f"Error fetching signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals/{username}")
async def get_user_signals(
    username: str,
    days: int = Query(7, ge=1, le=30),
    limit: int = Query(100, ge=1, le=500)
):
    """
    Get signals for a specific user within time window
    
    Returns filtered signals for detailed analysis.
    """
    try:
        db = MongoDB.get_db()
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        signals = await db.text_units_signals.find({
            "case_user": username,
            "processed_at": {"$gte": cutoff}
        }).sort("processed_at", -1).limit(limit).to_list(length=limit)
        
        # Format for JSON response
        for signal in signals:
            signal['_id'] = str(signal['_id'])
            if 'processed_at' in signal and signal['processed_at']:
                signal['processed_at'] = signal['processed_at'].isoformat()
            if 'timestamp' in signal and signal['timestamp']:
                signal['timestamp'] = signal['timestamp'].isoformat() if hasattr(signal['timestamp'], 'isoformat') else str(signal['timestamp'])
        
        return {
            "count": len(signals),
            "case_user": username,
            "days": days,
            "signals": signals
        }
        
    except Exception as e:
        logger.error(f"Error fetching signals for {username}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Statistics ==========

@router.get("/stats")
async def get_analytics_stats():
    """
    Get overall analytics statistics
    
    Returns counts and summaries for dashboard metrics.
    """
    try:
        db = MongoDB.get_db()
        
        # Count documents
        profiles_count = await db.case_risk_profiles.count_documents({})
        signals_count = await db.text_units_signals.count_documents({})
        summaries_count = await db.case_llm_summaries.count_documents({})
        
        # Count by risk level
        high_risk = await db.case_risk_profiles.count_documents({"risk_level": "High"})
        medium_risk = await db.case_risk_profiles.count_documents({"risk_level": "Medium"})
        low_risk = await db.case_risk_profiles.count_documents({"risk_level": "Low"})
        
        # Get recent activity
        recent_cutoff = datetime.utcnow() - timedelta(days=7)
        recent_signals = await db.text_units_signals.count_documents({
            "processed_at": {"$gte": recent_cutoff}
        })
        
        # Get average risk score
        pipeline = [
            {'$group': {
                '_id': None,
                'avg_risk_score': {'$avg': '$risk_score'},
                'max_risk_score': {'$max': '$risk_score'},
                'min_risk_score': {'$min': '$risk_score'}
            }}
        ]
        risk_stats = await db.case_risk_profiles.aggregate(pipeline).to_list(length=1)
        
        avg_risk = risk_stats[0]['avg_risk_score'] if risk_stats else 0
        max_risk = risk_stats[0]['max_risk_score'] if risk_stats else 0
        min_risk = risk_stats[0]['min_risk_score'] if risk_stats else 0
        
        return {
            "total_profiles": profiles_count,
            "total_signals": signals_count,
            "total_llm_summaries": summaries_count,
            "recent_signals_7d": recent_signals,
            "risk_breakdown": {
                "high": high_risk,
                "medium": medium_risk,
                "low": low_risk
            },
            "risk_score_stats": {
                "average": round(avg_risk, 2),
                "maximum": round(max_risk, 2),
                "minimum": round(min_risk, 2)
            },
            "last_updated": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Dashboard Data ==========

@router.get("/dashboard/cases")
async def get_dashboard_cases(
    priority: Optional[int] = Query(None, ge=1, le=3),
    limit: int = Query(20, ge=1, le=50)
):
    """
    Get cases for dashboard display with LLM summaries
    
    Returns enriched case data including risk profiles and latest summaries.
    This is the primary endpoint for the main dashboard view.
    """
    try:
        db = MongoDB.get_db()
        
        # Build query
        query = {}
        if priority:
            query['priority'] = priority
        
        # Get profiles
        profiles = await db.case_risk_profiles.find(
            query
        ).sort([
            ('priority', 1),
            ('risk_score', -1)
        ]).limit(limit).to_list(length=limit)
        
        # Enrich with LLM summaries and recent signals
        result = []
        for profile in profiles:
            profile['_id'] = str(profile['_id'])
            
            # Get latest summary
            summary = await db.case_llm_summaries.find_one(
                {"case_user": profile['case_user']},
                sort=[("generated_at", -1)]
            )
            
            if summary:
                summary['_id'] = str(summary['_id'])
                if 'generated_at' in summary:
                    summary['generated_at'] = summary['generated_at'].isoformat()
                profile['llm_summary'] = summary
            
            # Get recent signal count
            recent_cutoff = datetime.utcnow() - timedelta(days=7)
            recent_count = await db.text_units_signals.count_documents({
                "case_user": profile['case_user'],
                "processed_at": {"$gte": recent_cutoff}
            })
            profile['recent_signals_7d'] = recent_count
            
            result.append(profile)
        
        return {
            "count": len(result),
            "cases": result,
            "filters": {
                "priority": priority
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching dashboard cases: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/case/{case_user}/signals")
async def get_case_signals_timeline(
    case_user: str,
    days: int = Query(14, ge=1, le=30)
):
    """
    Get signal timeline for a specific case
    
    Returns time-series data for sentiment, distress, and distortion trends.
    Used for detailed case visualization.
    """
    try:
        db = MongoDB.get_db()
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Get signals
        signals = await db.text_units_signals.find({
            "case_user": case_user,
            "processed_at": {"$gte": cutoff}
        }).sort("processed_at", 1).to_list(length=None)
        
        # Format for timeline visualization
        timeline = []
        emotion_counts = {}
        distortion_categories = {}
        
        for signal in signals:
            # Basic timeline point
            point = {
                "date": signal['processed_at'].isoformat(),
                "sentiment_score": signal['sentiment_score'],
                "distress_score": signal.get('distress_score', 0),
                "distortion": signal['distortion_indicator'],
                "emotion": signal['emotion_label'],
                "text": signal['text'][:100] + "..." if len(signal['text']) > 100 else signal['text']
            }
            timeline.append(point)
            
            # Aggregate for statistics
            emotion = signal['emotion_label']
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
            
            if signal.get('distortion_category'):
                cat = signal['distortion_category']
                distortion_categories[cat] = distortion_categories.get(cat, 0) + 1
        
        # Calculate summary statistics
        total = len(signals)
        distress_count = sum(1 for s in signals if s.get('is_distress', False))
        distortion_count = sum(1 for s in signals if s.get('distortion_indicator', 0) == 1)
        
        # Get risk profile for context
        profile = await db.case_risk_profiles.find_one({"case_user": case_user})
        
        # Get latest summary
        summary = await db.case_llm_summaries.find_one(
            {"case_user": case_user},
            sort=[("generated_at", -1)]
        )
        
        return {
            "case_user": case_user,
            "days": days,
            "total_signals": total,
            "timeline": timeline,
            "statistics": {
                "distress_rate": distress_count / total if total > 0 else 0,
                "distortion_rate": distortion_count / total if total > 0 else 0,
                "emotion_distribution": emotion_counts,
                "distortion_categories": distortion_categories,
                "avg_sentiment": sum(s['sentiment_score'] for s in signals) / total if total > 0 else 0
            },
            "risk_profile": {
                "risk_score": profile.get('risk_score') if profile else None,
                "risk_level": profile.get('risk_level') if profile else None,
                "priority": profile.get('priority') if profile else None
            } if profile else None,
            "latest_summary": {
                "generated_at": summary['generated_at'].isoformat() if summary and 'generated_at' in summary else None,
                "executive_summary": summary.get('executive_summary') if summary else None
            } if summary else None
        }
        
    except Exception as e:
        logger.error(f"Error fetching timeline for {case_user}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Utility Endpoints ==========

@router.delete("/clear-signals")
async def clear_all_signals(confirm: bool = Query(False)):
    """
    Clear all signals from database (use with caution)
    
    Requires confirmation parameter for safety.
    """
    if not confirm:
        raise HTTPException(status_code=400, detail="Must set confirm=true to delete all signals")
    
    try:
        db = MongoDB.get_db()
        
        # Delete all signals
        signals_result = await db.text_units_signals.delete_many({})
        
        # Also clear profiles and summaries
        profiles_result = await db.case_risk_profiles.delete_many({})
        summaries_result = await db.case_llm_summaries.delete_many({})
        
        return {
            "status": "success",
            "message": "All analytics data cleared",
            "deleted": {
                "signals": signals_result.deleted_count,
                "profiles": profiles_result.deleted_count,
                "summaries": summaries_result.deleted_count
            }
        }
        
    except Exception as e:
        logger.error(f"Error clearing signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pipeline-status")
async def get_pipeline_status():
    """
    Get status of last pipeline run
    
    Returns information about the most recent pipeline execution.
    """
    try:
        db = MongoDB.get_db()
        
        # Get latest pipeline run
        latest = await db.pipeline_runs.find_one(
            sort=[("timestamp", -1)]
        )
        
        if not latest:
            return {
                "status": "no_runs",
                "message": "No pipeline runs found"
            }
        
        # Format response
        latest['_id'] = str(latest['_id'])
        if 'timestamp' in latest:
            latest['timestamp'] = latest['timestamp'].isoformat()
        
        return {
            "status": "success",
            "last_run": latest
        }
        
    except Exception as e:
        logger.error(f"Error fetching pipeline status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
