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

@router.get("/dashboard-cases", response_model=Dict)
async def get_dashboard_cases_with_llm():
    """
    Get dashboard cases with LLM-enhanced summaries and categories
    This is the main endpoint for the frontend dashboard
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
            # Use LLM category if available, otherwise determine from risk
            category = profile.get('llm_category', profile.get('risk_level', 'Monitoring'))
            
            # Map to consistent categories
            if profile.get('risk_level') == 'High':
                if profile.get('risk_score', 0) > 80:
                    category = "Critical"
                else:
                    category = "High Risk"
            elif profile.get('risk_level') == 'Medium':
                category = "Moderate Risk"
            else:
                category = "Low Risk"
            
            # Get LLM summary or generate from metrics
            summary = profile.get('llm_explanation', '')
            if not summary:
                if profile.get('risk_level') == 'High':
                    summary = f"High-risk case with {profile.get('distress_emotion_rate', 0):.1%} distress rate."
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