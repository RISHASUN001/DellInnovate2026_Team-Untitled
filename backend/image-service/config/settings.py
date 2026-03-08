"""
Configuration — loaded once at startup from environment variables / .env file.

All infrastructure-specific settings are kept here so business logic never
imports os.environ directly.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor all relative paths to the image-service project root regardless of
# which directory uvicorn / the test-runner is started from.
_SERVICE_ROOT = Path(__file__).parent.parent.resolve()

# Look for .env in multiple locations (root first, then service directory)
# From settings.py: config/ -> image-service/ -> backend/ -> project-root/
_PROJECT_ROOT = _SERVICE_ROOT.parent.parent  # Go up to project root
_ROOT_ENV = _PROJECT_ROOT / ".env"
_LOCAL_ENV = _SERVICE_ROOT / ".env"

# Use root .env if it exists, otherwise local .env
_ENV_FILE = _ROOT_ENV if _ROOT_ENV.exists() else _LOCAL_ENV

# Debug: Print which env file will be used (helps with troubleshooting)
import logging
_logger = logging.getLogger(__name__)
if _ROOT_ENV.exists():
    _logger.debug("Using root .env file: %s", _ROOT_ENV)
else:
    _logger.debug("Root .env not found, using local: %s", _LOCAL_ENV)


class Settings(BaseSettings):
    """Application settings resolved from envvars or a .env file."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Paths — defaults are resolved relative to the service root so they
    # work correctly no matter where uvicorn is launched from.
    # ------------------------------------------------------------------
    input_folder: Path = _SERVICE_ROOT / "data" / "post_images"
    output_folder: Path = _SERVICE_ROOT / "outputs"

    @model_validator(mode="after")
    def _resolve_paths(self) -> "Settings":
        """Make relative path overrides absolute using _SERVICE_ROOT."""
        if not self.input_folder.is_absolute():
            self.input_folder = (_SERVICE_ROOT / self.input_folder).resolve()
        if not self.output_folder.is_absolute():
            self.output_folder = (_SERVICE_ROOT / self.output_folder).resolve()
        return self

    # ------------------------------------------------------------------
    # Model identifiers
    # ------------------------------------------------------------------
    sentiment_model: str = "cardiffnlp/twitter-roberta-base-sentiment-latest"
    # Use a stronger default facial emotion classifier
    emotion_model: str = "dima806/facial_emotions_image_detection"
    
    # ------------------------------------------------------------------
    # VLM Model Selection
    # Choose which Vision-Language Model to use:
    #   - "smolvlm": HuggingFaceTB/SmolVLM-Instruct (accurate but SLOW on Apple Silicon)
    #   - "blip2":   Salesforce/blip2-opt-2.7b (FAST on Apple Silicon, good quality)
    #   - "llava":   llava-hf/llava-v1.6-mistral-7b-hf (balanced speed/quality)
    #   - "qwen":    Qwen/Qwen2.5-VL-72B via OpenRouter API (FASTEST, cloud-based)
    # ------------------------------------------------------------------
    vlm_model: str = "blip2"  # Change this to switch models!
    
    # ------------------------------------------------------------------
    # OpenRouter API Configuration (for Qwen VLM)
    # ------------------------------------------------------------------
    openrouter_api_key: str = "sk-or-placeholder"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    qwen_model: str = "qwen/qwen2.5-vl-72b-instruct"

    # ------------------------------------------------------------------
    # Inference device (cpu | cuda | mps)
    # Auto-detected by default, but can be overridden via env var
    # ------------------------------------------------------------------
    device: str | None = None
    
    @model_validator(mode="after")
    def _set_device(self) -> "Settings":
        """Auto-detect device if not explicitly set."""
        if self.device is None:
            from config.device_utils import get_device  # noqa: PLC0415
            self.device = get_device()
        return self


    # ------------------------------------------------------------------
    # OCR settings removed (SmolVLM replaces OCR pipeline)

    # ------------------------------------------------------------------
    # Image preprocessing
    # ------------------------------------------------------------------
    # Set to 0 to disable resizing before OCR.
    max_image_side_px: int = 1024
    
    # ------------------------------------------------------------------
    # Performance Optimization
    # ------------------------------------------------------------------
    # Use optimized preprocessing (256x256, JPEG compression)
    use_optimized_preprocessing: bool = False
    # Target size for optimized preprocessing
    optimized_target_size: int = 256
    # JPEG quality for optimization (1-100)
    optimized_jpeg_quality: int = 85
    # Enable preprocessing cache
    enable_preprocessing_cache: bool = False
    # Pixel quantization (abstractification) - None to disable
    pixel_quantization: int | None = None
    
    # ------------------------------------------------------------------
    # Parallel Processing
    # ------------------------------------------------------------------
    # Enable parallel processing (faster but uses more memory)
    enable_parallel_processing: bool = False
    # Number of parallel workers
    parallel_workers: int = 4
    # Batch size for processing
    batch_size: int = 8
    # Processing mode: 'parallel' | 'batched' | 'streaming' | 'sequential'
    processing_mode: str = "sequential"

    # ------------------------------------------------------------------
    # Sentiment thresholds
    # ------------------------------------------------------------------
    sentiment_confidence_threshold: float = 0.0

    # ------------------------------------------------------------------
    # Processing caps (useful for local dev)
    # ------------------------------------------------------------------
    max_images: int = 0  # 0 = no cap

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    log_level: str = "INFO"

    # ------------------------------------------------------------------
    # MongoDB Configuration
    # ------------------------------------------------------------------
    mongodb_uri: str = "mongodb+srv://rishikamehta2004:rishu2004@cluster0.1yrcnpc.mongodb.net/dellinnovate?retryWrites=true&w=majority"
    mongodb_db_name: str = "dellinnovate"
    mongodb_collection_name: str = "image_analysis_results"


# Singleton — imported everywhere that needs settings
settings = Settings()
