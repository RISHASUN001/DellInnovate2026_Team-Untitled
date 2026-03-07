"""
LLM Routes for enriched risk profiles
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict
from loguru import logger
from datetime import datetime

from config.database import MongoDB
from analytics.feature_engineering import BehavioralFeatureEngineer
from analytics.llm_integration import LLMSummarizer

router = APIRouter(prefix="/api/llm", tags=["LLM"])

@router.get("/analyze/{username}")
async def analyze_user_with_llm(
    username: str,
    window_days: int = Query(7, description="Analysis window in days")
):
    """
    Get enriched risk profile with LLM analysis for a specific user
    """
    try:
        engineer = BehavioralFeatureEngineer()
        
        # Compute enriched profile
        enriched_profile = await engineer.compute_enriched_risk_profile(
            case_user=username,
            window_days=window_days,
            use_llm=True
        )
        
        if not enriched_profile:
            raise HTTPException(status_code=404, detail=f"No data found for user: {username}")
        
        return {
            "status": "success",
            "data": enriched_profile
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing user {username}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/batch-analyze")
async def batch_analyze_users(
    usernames: List[str],
    window_days: int = Query(7, description="Analysis window in days")
):
    """
    Get enriched risk profiles for multiple users
    """
    try:
        engineer = BehavioralFeatureEngineer()
        results = []
        
        for username in usernames:
            try:
                enriched = await engineer.compute_enriched_risk_profile(
                    case_user=username,
                    window_days=window_days,
                    use_llm=True
                )
                if enriched:
                    results.append(enriched)
            except Exception as e:
                logger.error(f"Error processing {username}: {e}")
                continue
        
        return {
            "status": "success",
            "processed": len(results),
            "total_requested": len(usernames),
            "data": results
        }
        
    except Exception as e:
        logger.error(f"Error in batch analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard-cases")
async def get_dashboard_cases_with_llm():
    """
    Get dashboard cases with LLM-enhanced summaries and categories
    This is the main endpoint for the frontend dashboard
    """
    try:
        # Get risk profiles from database
        profiles_collection = MongoDB.get_collection("case_risk_profiles")
        
        # Get all profiles, sorted by risk score (highest first)
        cursor = profiles_collection.find().sort("risk_score", -1).limit(50)
        profiles = await cursor.to_list(length=50)
        
        # Transform to dashboard format
        dashboard_cases = []
        
        for idx, profile in enumerate(profiles):
            # Use LLM category if available, otherwise determine from risk
            category = profile.get('llm_category', profile.get('risk_level', 'Monitoring'))
            
            # Map to consistent categories
            category_map = {
                'High': 'Self-Harm Ideation' if profile.get('risk_score', 0) > 80 else 'High Risk',
                'Medium': 'Anxiety' if profile.get('distress_emotion_rate', 0) > 0.3 else 'Moderate Risk',
                'Low': 'Monitoring' if profile.get('total_comments_received', 0) > 0 else 'Low Risk'
            }
            
            # Get LLM summary or generate from metrics
            summary = profile.get('llm_summary', '')
            if not summary:
                if profile.get('risk_level') == 'High':
                    summary = f"High-risk case with {profile.get('distress_emotion_rate', 0):.1%} distress rate and {profile.get('distortion_rate', 0):.1%} cognitive distortion."
                else:
                    summary = f"{profile.get('risk_level')} risk case. Monitor regularly."
            
            # Build signals list
            signals = profile.get('key_signals', [])
            if not signals:
                signals = [
                    f"Distress rate: {profile.get('distress_emotion_rate', 0):.1%}",
                    f"Distortion rate: {profile.get('distortion_rate', 0):.1%}",
                    f"Risk score: {profile.get('risk_score', 0):.1f}"
                ]
            
            # Create dashboard case
            case = {
                'id': idx + 1,
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
                'signals': signals[:5],  # Limit to 5 signals
                'summary': summary,
                'recommendations': profile.get('llm_recommendations', [
                    "Monitor case regularly",
                    "Review signals weekly"
                ]),
                'nlp_metrics': {
                    'total_signals': profile.get('total_text_units', 0),
                    'distress_count': profile.get('distress_emotion_count', 0),
                    'distortion_count': profile.get('distortion_count', 0),
                    'avg_sentiment': profile.get('avg_sentiment_score', 0),
                    'distress_rate': profile.get('distress_emotion_rate', 0),
                    'emotion_distribution': profile.get('emotion_distribution', {})
                },
                'has_llm_analysis': profile.get('has_llm_analysis', False)
            }
            
            dashboard_cases.append(case)
        
        return {
            "status": "success",
            "cases": dashboard_cases
        }
        
    except Exception as e:
        logger.error(f"Error getting dashboard cases: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/refresh-llm-analysis")
async def refresh_llm_analysis(username: Optional[str] = None):
    """
    Refresh LLM analysis for a user or all users
    """
    try:
        engineer = BehavioralFeatureEngineer()
        summarizer = LLMSummarizer()
        profiles_collection = MongoDB.get_collection("case_risk_profiles")
        
        if username:
            # Get specific user profile
            profile = await profiles_collection.find_one({"case_user": username})
            if not profile:
                raise HTTPException(status_code=404, detail=f"User {username} not found")
            
            # Generate new LLM insights
            llm_insights = await summarizer.summarize_risk_profile(profile)
            
            # Update profile
            await profiles_collection.update_one(
                {"case_user": username},
                {"$set": {
                    "llm_summary": llm_insights['summary'],
                    "llm_category": llm_insights['llm_category'],
                    "llm_recommendations": llm_insights['recommendations'],
                    "llm_generated_at": llm_insights['generated_at'],
                    "has_llm_analysis": True
                }}
            )
            
            return {"status": "success", "message": f"LLM analysis refreshed for {username}"}
        
        else:
            # Refresh all profiles
            cursor = profiles_collection.find()
            profiles = await cursor.to_list(length=None)
            
            updated = 0
            for profile in profiles:
                try:
                    llm_insights = await summarizer.summarize_risk_profile(profile)
                    await profiles_collection.update_one(
                        {"_id": profile["_id"]},
                        {"$set": {
                            "llm_summary": llm_insights['summary'],
                            "llm_category": llm_insights['llm_category'],
                            "llm_recommendations": llm_insights['recommendations'],
                            "llm_generated_at": llm_insights['generated_at'],
                            "has_llm_analysis": True
                        }}
                    )
                    updated += 1
                except Exception as e:
                    logger.error(f"Error updating {profile.get('case_user')}: {e}")
                    continue
            
            return {
                "status": "success",
                "message": f"LLM analysis refreshed for {updated}/{len(profiles)} profiles"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing LLM analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))