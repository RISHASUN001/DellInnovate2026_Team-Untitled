"""
FastAPI application entry point for image-service.

Startup sequence
----------------
1. Configure structured logging.
2. Warm-load all ML models exactly once (preprocessing, OCR, sentiment, emotion).
3. Wire up the dependency graph (adapters → ports → use cases).
4. Register API routes.

The server is started via uvicorn (see Dockerfile CMD and docker-compose).
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from adapters.emotion_adapter import HuggingFaceEmotionAdapter
from adapters.ocr_adapter import EasyOcrAdapter
from adapters.preprocessing_adapter import PillowPreprocessingAdapter
from adapters.sentiment_adapter import HuggingFaceSentimentAdapter
from adapters.storage_adapter import CsvStorageAdapter
from api.routes import router, set_runner
from application.use_cases import ProcessSingleImage, RunBatchProcessing
from config.settings import settings


# ---------------------------------------------------------------------------
# Logging — structured, level-configurable via settings
# ---------------------------------------------------------------------------

def _configure_logging() -> None:
    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format=log_format,
        stream=sys.stdout,
    )


# ---------------------------------------------------------------------------
# Lifespan — warm-load models once at startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler.

    All heavy initialisations (model loading) happen here so they run once
    at server start rather than on the first request.
    """
    logger = logging.getLogger(__name__)
    logger.info("image-service starting up…")

    # Instantiate adapters (model warm-loading happens in __init__)
    preprocessor = PillowPreprocessingAdapter()
    ocr = EasyOcrAdapter()
    sentiment = HuggingFaceSentimentAdapter()
    emotion = HuggingFaceEmotionAdapter()
    storage = CsvStorageAdapter()

    # Wire use cases
    process_single = ProcessSingleImage(
        preprocessor=preprocessor,
        ocr=ocr,
        sentiment=sentiment,
        emotion=emotion,
    )
    runner = RunBatchProcessing(
        process_single=process_single,
        storage=storage,
    )

    # Inject runner into route layer
    set_runner(runner)
    logger.info("All models warm. image-service is ready.")

    yield

    logger.info("image-service shutting down.")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    _configure_logging()

    app = FastAPI(
        title="Image Service",
        description=(
            "Microservice for batch OCR→sentiment and facial emotion detection "
            "on Instagram post images, following hexagonal architecture."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    return app


app = create_app()


# ---------------------------------------------------------------------------
# Dev/standalone entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8002,
        reload=False,
        log_level=settings.log_level.lower(),
    )
