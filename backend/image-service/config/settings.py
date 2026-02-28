"""
Configuration — loaded once at startup from environment variables / .env file.

All infrastructure-specific settings are kept here so business logic never
imports os.environ directly.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor all relative paths to the image-service project root regardless of
# which directory uvicorn / the test-runner is started from.
_SERVICE_ROOT = Path(__file__).parent.parent.resolve()


class Settings(BaseSettings):
    """Application settings resolved from envvars or a .env file."""

    model_config = SettingsConfigDict(
        env_file=str(_SERVICE_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Paths — defaults are resolved relative to the service root so they
    # work correctly no matter where uvicorn is launched from.
    # ------------------------------------------------------------------
    input_folder: Path = _SERVICE_ROOT / "data" / "post_images"
    output_folder: Path = _SERVICE_ROOT / "outputs"

    # ------------------------------------------------------------------
    # Model identifiers
    # ------------------------------------------------------------------
    sentiment_model: str = "cardiffnlp/twitter-roberta-base-sentiment-latest"
    emotion_model: str = "dima806/facial_emotions_image_detection"

    # ------------------------------------------------------------------
    # Inference device (cpu | cuda | mps)
    # ------------------------------------------------------------------
    device: str = "cpu"


    # ------------------------------------------------------------------
    # OCR settings removed (SmolVLM replaces OCR pipeline)

    # ------------------------------------------------------------------
    # Image preprocessing
    # ------------------------------------------------------------------
    # Set to 0 to disable resizing before OCR.
    max_image_side_px: int = 1024

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


# Singleton — imported everywhere that needs settings
settings = Settings()
