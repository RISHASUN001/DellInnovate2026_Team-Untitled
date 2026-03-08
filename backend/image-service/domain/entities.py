"""
Domain entities — the heart of the hexagonal architecture.

All types here are plain Python dataclasses with *no* dependencies on
infrastructure, frameworks, or external libraries.  They cross every port
boundary, so they must stay stable and free of side-effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ImageMetadata:
    """Parsed metadata extracted from an image filename.

    Filename convention:  <ig_handle>__<YYYYMMDD>__<index>.(jpg|png)
    """

    ig_handle: str
    post_date: date
    image_index: int

    def __str__(self) -> str:
        return (
            f"{self.ig_handle} | {self.post_date.isoformat()} | idx={self.image_index}"
        )


# ---------------------------------------------------------------------------
# Job / command
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ImageJob:
    """Represents a single unit of work: process one image file."""

    image_path: Path
    metadata: ImageMetadata

    @property
    def ig_handle(self) -> str:
        return self.metadata.ig_handle

    @property
    def post_date(self) -> date:
        return self.metadata.post_date

    @property
    def image_index(self) -> int:
        return self.metadata.image_index


# ---------------------------------------------------------------------------
# Pipeline result fragments
# ---------------------------------------------------------------------------


@dataclass
class OcrResult:
    """Raw output from the OCR pipeline step."""

    ocr_text_raw: str
    ocr_text_clean: str
    ocr_char_count: int
    ocr_word_count: int
    ocr_detected_bool: bool  # True if text surpassed the minimum threshold


@dataclass
class SentimentResult:
    """Output from the sentiment inference step."""

    sentiment_label: str
    sentiment_score: float


@dataclass
class EmotionResult:
    """Output from the facial-emotion detection pipeline."""

    face_detected_bool: bool
    emotion_label: str
    emotion_score: float
    model_name: str


# ---------------------------------------------------------------------------
# Aggregate record
# ---------------------------------------------------------------------------


@dataclass
class ImageRecord:
    """Aggregate that holds all pipeline results for a single image."""

    job: ImageJob
    ocr_result: Optional[OcrResult] = None
    sentiment_result: Optional[SentimentResult] = None
    emotion_result: Optional[EmotionResult] = None
    processed_at: datetime = field(default_factory=datetime.utcnow)
    error_ocr: Optional[str] = None
    error_emotion: Optional[str] = None

    # New fields for VLM-based emotional reasoning and fusion
    image_description: Optional[str] = None  # What is happening in the image (scene, people, actions, posture)
    vlm_emotion_description: Optional[str] = None
    fused_emotion_assessment: Optional[str] = None

    # ------------------------------------------------------------------
    # Convenience accessors used by the storage adapter
    # ------------------------------------------------------------------

    @property
    def image_path_str(self) -> str:
        return str(self.job.image_path)

    @property
    def ig_handle(self) -> str:
        return self.job.ig_handle

    @property
    def post_date(self) -> date:
        return self.job.post_date

    @property
    def image_index(self) -> int:
        return self.job.image_index

    @property
    def has_error(self) -> bool:
        """Check if there were any errors during processing."""
        return bool(self.error_ocr or self.error_emotion)
