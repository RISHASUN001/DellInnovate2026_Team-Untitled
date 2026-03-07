from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from loguru import logger
from contextlib import asynccontextmanager

from config.database import MongoDB
from routes.scraper_routes import router as scraper_router

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
    title="Instagram Scraper API",
    description="API for scraping Instagram data using Scrapfly",
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

@app.get("/")
async def root():
    return {
        "message": "Instagram Scraper API",
        "version": "1.0.0",
        "endpoints": {
            "scrape_user": "/api/scraper/scrape/user/{username}",
            "scrape_multiple": "/api/scraper/scrape",
            "scrape_post": "/api/scraper/scrape/post",
            "get_users": "/api/scraper/users",
            "get_user": "/api/scraper/user/{username}",
            "get_post": "/api/scraper/post/{shortcode}",
            "get_job": "/api/scraper/job/{job_id}"
        }
    }

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