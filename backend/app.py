from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from loguru import logger
from contextlib import asynccontextmanager

from config.database import MongoDB
from routes.scraper_routes import router as scraper_router
from routes.analytics_routes import router as analytics_router
from routes.nlp_routes import router as nlp_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up...")
    await MongoDB.connect_db()
    yield
    # Shutdown
    logger.info("Shutting down...")
    await MongoDB.close_db()

# Create FastAPI app
app = FastAPI(
    title="Instagram Scraper & Analytics API",
    description="API for scraping Instagram data and detecting emotional distress signals",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(scraper_router)
app.include_router(analytics_router)
app.include_router(nlp_router)

@app.get("/")
async def root():
    return {
        "message": "Instagram Comment Analysis Pipeline - End-to-End NLP Analysis",
        "version": "2.0.0",
        "description": "Unified pipeline for analyzing Instagram comments with multilingual sentiment and emotion detection",
        "features": [
            "Instagram data scraping",
            "Multilingual sentiment analysis",
            "Emotion detection (sadness, anger, fear, joy, love, surprise)",
            "Advanced cognitive distortion detection (8 types)",
            "Sentiment volatility and emotional pattern analysis",
            "User engagement and behavioral pattern analysis",
            "Comprehensive risk assessment and prioritization",
            "CSV and JSON export formats"
        ],
        "pipeline": {
            "unified_analysis": "Use instagram_analysis_pipeline.py for end-to-end analysis",
            "web_interface": "/docs for API documentation"
        },
        "endpoints": {
            "unified_pipeline": {
                "analyze_user": "/api/unified-pipeline/analyze-user",
                "analyze_existing": "/api/unified-pipeline/analyze-existing"
            },
            "scraper": {
                "scrape_user": "/api/scraper/scrape/user/{username}",
                "scrape_multiple": "/api/scraper/scrape",
                "scrape_post": "/api/scraper/scrape/post",
                "get_users": "/api/scraper/users",
                "get_user": "/api/scraper/user/{username}",
                "get_post": "/api/scraper/post/{shortcode}",
                "get_job": "/api/scraper/job/{job_id}"
            },
            "nlp": {
                "analyze_text": "/api/nlp/analyze/text",
                "analyze_comments": "/api/nlp/analyze/comments",
                "analyze_user": "/api/nlp/analyze/user",
                "export_signal_csv": "/api/nlp/export/signal-csv",
                "signal_dataframe": "/api/nlp/signal-dataframe",
                "cognitive_distortions": "/api/nlp/pattern-analysis/cognitive-distortions",
                "sentiment_volatility": "/api/nlp/pattern-analysis/sentiment-volatility",
                "engagement_patterns": "/api/nlp/pattern-analysis/engagement-patterns",
                "comprehensive_pattern_analysis": "/api/nlp/pattern-analysis/comprehensive",
                "health_check": "/api/nlp/health"
            },
            "docs": "/docs"
        },
        "models": {
            "sentiment": "cardiffnlp/twitter-xlm-roberta-base-sentiment (Multilingual)",
            "emotion": "cardiffnlp/twitter-roberta-base-emotion-multilabel-latest (English)",
            "pattern_analysis": {
                "cognitive_distortions": "8 distortion types (all-or-nothing, catastrophizing, personalization, etc.)",
                "sentiment_volatility": "Temporal emotion tracking and rapid shift detection",
                "engagement_patterns": "Behavioral analysis (crisis bursts, withdrawal patterns, etc.)",
                "risk_assessment": "Comprehensive scoring and recommendation system"
            }
        }
    }

# Unified Pipeline Endpoints
@app.post("/api/unified-pipeline/analyze-user")
async def unified_pipeline_analyze_user(request: dict):
    """
    Unified pipeline endpoint to analyze an Instagram user end-to-end
    """
    try:
        from instagram_analysis_pipeline import InstagramAnalysisPipeline
        
        username = request.get("username")
        if not username:
            raise HTTPException(status_code=400, detail="Username is required")
        
        # Initialize pipeline
        pipeline = InstagramAnalysisPipeline()
        
        # Run analysis
        result = await pipeline.analyze_instagram_user(
            username=username,
            scrape_comments=request.get("scrape_comments", True),
            export_csv=request.get("export_csv", True)
        )
        
        return {
            "status": "success",
            "username": username,
            "analysis": result,
            "message": f"Completed analysis for @{username}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")

@app.post("/api/unified-pipeline/analyze-existing")  
async def unified_pipeline_analyze_existing(request: dict):
    """
    Unified pipeline endpoint to analyze existing MongoDB data
    """
    try:
        from instagram_analysis_pipeline import InstagramAnalysisPipeline
        
        username = request.get("username")
        if not username:
            raise HTTPException(status_code=400, detail="Username is required")
        
        # Initialize pipeline
        pipeline = InstagramAnalysisPipeline()
        
        # Run analysis on existing data
        result = await pipeline.analyze_from_existing_data(
            username=username,
            export_csv=request.get("export_csv", True)
        )
        
        return {
            "status": "success", 
            "username": username,
            "analysis": result,
            "message": f"Completed analysis of existing data for @{username}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )