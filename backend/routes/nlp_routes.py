"""
API Routes for NLP Signal Pipeline
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from typing import List, Optional
from pydantic import BaseModel
from loguru import logger
import os
from datetime import datetime

from services.nlp_service import get_nlp_service
from services.pattern_analysis_service import get_pattern_service


router = APIRouter(
    prefix="/api/nlp",
    tags=["nlp"]
)


# Request/Response Models
class AnalyzeTextRequest(BaseModel):
    text: str


class AnalyzeTextResponse(BaseModel):
    text: str
    emotions: dict
    primary_emotion: Optional[str]
    primary_emotion_score: Optional[float]
    sentiment: Optional[str]
    sentiment_score: float
    distortion_indicator: bool
    distortion_score: float


class AnalyzeCommentsRequest(BaseModel):
    usernames: Optional[List[str]] = None
    limit: Optional[int] = None
    source: str = "posts"  # "posts" or "comment_users"


class AnalyzeUserRequest(BaseModel):
    username: str
    limit: Optional[int] = None
    include_pattern_analysis: Optional[bool] = True


class PatternAnalysisRequest(BaseModel):
    username: str
    comments: List[dict]  # Pre-analyzed comment data


class ExportSignalCSVRequest(BaseModel):
    usernames: Optional[List[str]] = None
    limit: Optional[int] = None
    source: str = "posts"
    filename: Optional[str] = None


@router.post("/analyze/text", response_model=AnalyzeTextResponse)
async def analyze_text(request: AnalyzeTextRequest):
    """
    Analyze a single text for emotion and sentiment
    
    - **text**: The text to analyze
    """
    try:
        nlp = get_nlp_service()
        result = nlp.analyze_text(request.text)
        return result
    except Exception as e:
        logger.error(f"Error analyzing text: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/comments")
async def analyze_comments(request: AnalyzeCommentsRequest):
    """
    Analyze comments from posts or comment users
    
    - **usernames**: Optional list of usernames to filter
    - **limit**: Optional limit on number of posts to process
    - **source**: Source of comments ("posts" or "comment_users")
    """
    try:
        nlp = get_nlp_service()
        
        if request.source == "posts":
            results = await nlp.analyze_comments_from_posts(
                usernames=request.usernames,
                limit=request.limit
            )
        elif request.source == "comment_users":
            results = await nlp.analyze_comment_users(
                usernames=request.usernames
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid source. Must be 'posts' or 'comment_users'"
            )
        
        return {
            "total_comments": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error analyzing comments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export/signal-csv")
async def export_signal_csv(request: ExportSignalCSVRequest):
    """
    Export analyzed comments to Signal CSV format
    
    - **usernames**: Optional list of usernames to filter
    - **limit**: Optional limit on number of posts to process
    - **source**: Source of comments ("posts" or "comment_users")
    - **filename**: Optional custom filename (without extension)
    
    Returns a downloadable CSV file
    """
    try:
        nlp = get_nlp_service()
        
        # Create output directory if it doesn't exist
        output_dir = "/home/st1/personal/DellInnovate2026_Team-Untitled/backend/exports"
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate filename
        if request.filename:
            filename = f"{request.filename}.csv"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"signal_data_{timestamp}.csv"
        
        output_path = os.path.join(output_dir, filename)
        
        # Export to CSV
        await nlp.export_signal_csv(
            output_path=output_path,
            usernames=request.usernames,
            source=request.source,
            limit=request.limit
        )
        
        # Return the file for download
        return FileResponse(
            path=output_path,
            filename=filename,
            media_type="text/csv"
        )
        
    except Exception as e:
        logger.error(f"Error exporting signal CSV: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signal-dataframe")
async def get_signal_dataframe(
    usernames: Optional[List[str]] = Query(None),
    limit: Optional[int] = Query(None),
    source: str = Query("posts")
):
    """
    Get signal data as JSON (without downloading CSV)
    
    - **usernames**: Optional list of usernames to filter
    - **limit**: Optional limit on number of posts to process
    - **source**: Source of comments ("posts" or "comment_users")
    """
    try:
        nlp = get_nlp_service()
        
        # Get analyzed comments
        if source == "posts":
            analyzed_comments = await nlp.analyze_comments_from_posts(
                usernames=usernames,
                limit=limit
            )
        elif source == "comment_users":
            analyzed_comments = await nlp.analyze_comment_users(
                usernames=usernames
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid source. Must be 'posts' or 'comment_users'"
            )
        
        # Create DataFrame and convert to dict
        df = nlp.create_signal_dataframe(analyzed_comments)
        
        return {
            "total_rows": len(df),
            "columns": list(df.columns),
            "data": df.to_dict(orient='records'),
            "summary": {
                "distortion_high": len(df[df['Distortion_Indicator'] == True]),
                "distortion_low": len(df[df['Distortion_Indicator'] == False]),
                "emotions_breakdown": {
                    "sadness": len(df[df['Emotion_Label'] == 'sadness']),
                    "anger": len(df[df['Emotion_Label'] == 'anger']),
                    "fear": len(df[df['Emotion_Label'] == 'fear']),
                    "joy": len(df[df['Emotion_Label'] == 'joy']),
                    "love": len(df[df['Emotion_Label'] == 'love']),
                    "surprise": len(df[df['Emotion_Label'] == 'surprise']),
                },
                "sentiment_breakdown": {
                    "positive": len(df[df['Sentiment'] == 'positive']),
                    "neutral": len(df[df['Sentiment'] == 'neutral']),
                    "negative": len(df[df['Sentiment'] == 'negative']),
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting signal dataframe: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def nlp_health_check():
    """Check if NLP service is healthy"""
    try:
        nlp = get_nlp_service()
        test_result = nlp.analyze_text("This is a test message")
        
        return {
            "status": "healthy",
            "models_loaded": {
                "emotion_analyzer": nlp.emotion_analyzer is not None,
                "sentiment_analyzer": nlp.sentiment_analyzer is not None
            },
            "test_analysis": test_result
        }
    except Exception as e:
        logger.error(f"NLP health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@router.post("/analyze/user")
async def analyze_user_comprehensive(request: AnalyzeUserRequest):
    """
    Comprehensive analysis for a single user including pattern analysis
    
    - **username**: Instagram username to analyze
    - **limit**: Optional limit on number of comments to analyze
    - **include_pattern_analysis**: Whether to include comprehensive pattern analysis
    """
    try:
        nlp = get_nlp_service()
        result = await nlp.analyze_user_comments(
            username=request.username,
            limit=request.limit,
            include_pattern_analysis=request.include_pattern_analysis
        )
        
        return {
            "status": "success",
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Error in comprehensive user analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pattern-analysis/cognitive-distortions")
async def analyze_cognitive_distortions(request: dict):
    """
    Analyze text for cognitive distortion patterns
    
    Body:
        {
            "text": "Text to analyze for cognitive distortions"
        }
    """
    try:
        text = request.get("text")
        if not text:
            raise HTTPException(status_code=400, detail="Text is required")
        
        pattern_service = get_pattern_service()
        result = pattern_service.detect_cognitive_distortions(text)
        
        return {
            "status": "success",
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Error analyzing cognitive distortions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pattern-analysis/sentiment-volatility")
async def analyze_sentiment_volatility(request: PatternAnalysisRequest):
    """
    Analyze sentiment volatility patterns for a user
    
    - **username**: Username for identification
    - **comments**: List of analyzed comment data with sentiment scores
    """
    try:
        pattern_service = get_pattern_service()
        result = pattern_service.analyze_sentiment_volatility(
            user_comments=request.comments
        )
        
        return {
            "status": "success",
            "username": request.username,
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Error analyzing sentiment volatility: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pattern-analysis/engagement-patterns")
async def analyze_engagement_patterns(request: PatternAnalysisRequest):
    """
    Analyze user engagement and behavioral patterns
    
    - **username**: Username for identification
    - **comments**: List of analyzed comment data with timestamps
    """
    try:
        pattern_service = get_pattern_service()
        result = pattern_service.analyze_engagement_patterns(
            user_comments=request.comments
        )
        
        return {
            "status": "success", 
            "username": request.username,
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Error analyzing engagement patterns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pattern-analysis/comprehensive")
async def analyze_user_patterns_comprehensive(request: PatternAnalysisRequest):
    """
    Comprehensive pattern analysis combining all methods
    
    - **username**: Username for identification
    - **comments**: List of analyzed comment data
    """
    try:
        pattern_service = get_pattern_service()
        result = pattern_service.analyze_user_comprehensive(
            user_comments=request.comments,
            username=request.username
        )
        
        return {
            "status": "success",
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Error in comprehensive pattern analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))
