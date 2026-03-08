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
from pathlib import Path
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from adapters.emotion_adapter import HuggingFaceEmotionAdapter
from adapters.smolvlm_adapter import SmolVLMAdapter
from adapters.blip2_adapter import BLIP2Adapter
from adapters.llava_adapter import LLaVAAdapter
from adapters.qwen_adapter import QwenAdapter
from adapters.preprocessing_adapter import PillowPreprocessingAdapter
from adapters.optimized_preprocessing_adapter import OptimizedPreprocessingAdapter
from adapters.sentiment_adapter import HuggingFaceSentimentAdapter
from adapters.mongodb_storage_adapter import MongoDBStorageAdapter
from adapters.storage_adapter import CsvStorageAdapter
from api.routes import router, set_runner
from application.use_cases import ProcessSingleImage, RunBatchProcessing
from application.parallel_processing import (
    ParallelBatchProcessing,
    ParallelProcessingConfig,
    StreamingBatchProcessing,
)
from application.file_watcher import start_file_watcher
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
    
    # Log which .env file is being used
    from config.settings import _ENV_FILE
    logger.info("Loading configuration from: %s", _ENV_FILE)

    # Select preprocessing adapter based on settings
    if settings.use_optimized_preprocessing:
        logger.info(
            "Using OPTIMIZED preprocessing: size=%d, quality=%d, cache=%s, quantize=%s",
            settings.optimized_target_size,
            settings.optimized_jpeg_quality,
            settings.enable_preprocessing_cache,
            settings.pixel_quantization,
        )
        preprocessor = OptimizedPreprocessingAdapter(
            target_size=settings.optimized_target_size,
            jpeg_quality=settings.optimized_jpeg_quality,
            enable_cache=settings.enable_preprocessing_cache,
            pixel_quantization=settings.pixel_quantization,
        )
    else:
        logger.info("Using STANDARD preprocessing (max_side=%d)", settings.max_image_side_px)
        preprocessor = PillowPreprocessingAdapter()

    # Instantiate VLM adapter based on settings.vlm_model
    vlm_choice = settings.vlm_model.lower()
    logger.info("Using VLM model: %s", vlm_choice)
    
    if vlm_choice == "qwen":
        vlm = QwenAdapter(device=settings.device)
        logger.info("✓ Qwen VLM adapter loaded (API-based, ultra-fast)")
    elif vlm_choice == "blip2":
        vlm = BLIP2Adapter(device=settings.device)
        logger.info("✓ BLIP-2 adapter loaded (optimized for Apple Silicon)")
    elif vlm_choice == "llava":
        vlm = LLaVAAdapter(device=settings.device)
        logger.info("✓ LLaVA adapter loaded (balanced speed/quality)")
    elif vlm_choice == "smolvlm":
        vlm = SmolVLMAdapter(device=settings.device)
        logger.info("✓ SmolVLM adapter loaded (accurate but slow on MPS)")
    else:
        logger.error("Invalid vlm_model='%s'. Choose 'qwen', 'smolvlm', 'blip2', or 'llava'.", vlm_choice)
        raise ValueError(f"Invalid vlm_model='{vlm_choice}'. Choose 'qwen', 'smolvlm', 'blip2', or 'llava'.")
    
    # Instantiate other ML adapters (model warm-loading happens in __init__)
    sentiment = HuggingFaceSentimentAdapter()
    emotion = HuggingFaceEmotionAdapter()
    storage = MongoDBStorageAdapter()
    
    # Initialize CSV storage adapter for VLM results (saved to data/analytics folder)
    csv_storage = CsvStorageAdapter(output_folder=Path(settings.input_folder).parent / "data" / "analytics")
    logger.info("CSV storage configured: %s", csv_storage._output_folder)

    # Wire use cases
    process_single = ProcessSingleImage(
        preprocessor=preprocessor,
        smolvlm=vlm,  # Pass selected VLM adapter
        sentiment=sentiment,
        emotion=emotion,
    )
    
    # Make CSV storage available globally for file watcher
    app.state.csv_storage = csv_storage
    
    # Select processing runner based on settings
    processing_mode = settings.processing_mode.lower()
    
    if processing_mode == "parallel":
        logger.info("Using PARALLEL processing: workers=%d", settings.parallel_workers)
        config = ParallelProcessingConfig(
            max_workers=settings.parallel_workers,
            batch_size=settings.batch_size,
        )
        runner = ParallelBatchProcessing(
            process_single=process_single,
            storage=storage,
            config=config,
        )
        # Wrap execute_parallel to match RunBatchProcessing interface
        original_execute = runner.execute_parallel
        
        def wrapped_execute(input_folder=None, overwrite=False, max_images=0):
            from application.filename_parser import discover_images, parse_image_filename
            from domain.entities import ImageJob
            
            folder = input_folder or settings.input_folder
            cap = max_images if max_images > 0 else settings.max_images
            
            logger.info("Scanning '%s' for images…", folder)
            all_paths = discover_images(folder)
            logger.info("Found %d image files.", len(all_paths))
            
            jobs = []
            skipped = 0
            for path in all_paths:
                meta = parse_image_filename(path)
                if meta is None:
                    logger.debug("Skipping '%s' — filename does not match convention.", path.name)
                    skipped += 1
                    continue
                jobs.append(ImageJob(image_path=path, metadata=meta))
            
            if skipped:
                logger.warning("%d files skipped (did not match naming convention).", skipped)
            
            if cap and len(jobs) > cap:
                logger.info("Capping to %d images (max_images=%d).", cap, cap)
                jobs = jobs[:cap]
            
            return original_execute(jobs, overwrite=overwrite)
        
        runner.execute = wrapped_execute
        
    elif processing_mode == "batched":
        logger.info("Using BATCHED processing: workers=%d, batch=%d", settings.parallel_workers, settings.batch_size)
        config = ParallelProcessingConfig(
            max_workers=settings.parallel_workers,
            batch_size=settings.batch_size,
        )
        runner = ParallelBatchProcessing(
            process_single=process_single,
            storage=storage,
            config=config,
        )
        # Wrap execute_batched
        original_execute = runner.execute_batched
        
        def wrapped_execute(input_folder=None, overwrite=False, max_images=0):
            from application.filename_parser import discover_images, parse_image_filename
            from domain.entities import ImageJob
            
            folder = input_folder or settings.input_folder
            cap = max_images if max_images > 0 else settings.max_images
            
            logger.info("Scanning '%s' for images…", folder)
            all_paths = discover_images(folder)
            logger.info("Found %d image files.", len(all_paths))
            
            jobs = []
            skipped = 0
            for path in all_paths:
                meta = parse_image_filename(path)
                if meta is None:
                    skipped += 1
                    continue
                jobs.append(ImageJob(image_path=path, metadata=meta))
            
            if skipped:
                logger.warning("%d files skipped.", skipped)
            
            if cap and len(jobs) > cap:
                jobs = jobs[:cap]
            
            return original_execute(jobs, overwrite=overwrite)
        
        runner.execute = wrapped_execute
        
    elif processing_mode == "streaming":
        logger.info("Using STREAMING processing: chunk=%d, workers=%d", settings.batch_size, settings.parallel_workers)
        runner = StreamingBatchProcessing(
            process_single=process_single,
            storage=storage,
            chunk_size=settings.batch_size,
            max_workers=settings.parallel_workers,
        )
        # Wrap execute_streaming
        original_execute = runner.execute_streaming
        
        def wrapped_execute(input_folder=None, overwrite=False, max_images=0):
            from application.filename_parser import discover_images, parse_image_filename
            from domain.entities import ImageJob
            
            folder = input_folder or settings.input_folder
            cap = max_images if max_images > 0 else settings.max_images
            
            all_paths = discover_images(folder)
            
            jobs = []
            for path in all_paths:
                meta = parse_image_filename(path)
                if meta is not None:
                    jobs.append(ImageJob(image_path=path, metadata=meta))
            
            if cap and len(jobs) > cap:
                jobs = jobs[:cap]
            
            return original_execute(jobs, overwrite=overwrite)
        
        runner.execute = wrapped_execute
        
    else:
        logger.info("Using SEQUENTIAL processing (standard)")
        runner = RunBatchProcessing(
            process_single=process_single,
            storage=storage,
        )

    # Inject runner into route layer
    set_runner(runner)
    logger.info("All models warm. image-service is ready.")
    
    # Start file watcher for automatic processing
    watch_folder = Path(settings.input_folder)
    done_folder = watch_folder.parent / "done"
    observer = start_file_watcher(
        watch_folder=watch_folder,
        done_folder=done_folder,
        process_single=process_single,
        csv_storage=csv_storage,
        processing_delay=1.0,  # Wait 1 second before processing new files
        process_existing=False,  # Don't process existing images on startup (avoid blocking)
    )
    logger.info("🚀 File watcher active - drop images into %s", watch_folder)
    
    # Process existing images in background thread to avoid blocking startup
    import threading
    def process_existing_in_background():
        import time
        time.sleep(3)  # Wait for startup to complete
        from application.file_watcher import process_existing_images
        try:
            logger.info("🔄 Starting background processing of existing images...")
            process_existing_images(watch_folder, done_folder, process_single, csv_storage)
        except Exception as e:
            logger.error("Background processing failed: %s", e)
    
    bg_thread = threading.Thread(target=process_existing_in_background, daemon=True)
    bg_thread.start()

    yield
    
    # Stop file watcher on shutdown
    if observer:
        logger.info("Stopping file watcher...")
        observer.stop()
        observer.join()
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
        port=8004,
        reload=False,
        log_level=settings.log_level.lower(),
    )
