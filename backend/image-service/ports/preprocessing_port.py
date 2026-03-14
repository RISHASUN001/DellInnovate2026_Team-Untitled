"""
PreprocessingPort — abstract interface for image preprocessing.

Separating preprocessing from model inference lets us change the
pipeline (denoise, resize, EXIF orient …) without touching adapters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from PIL import Image


class PreprocessingPort(ABC):
    """Load an image file and return a ready-to-infer PIL Image."""

    @abstractmethod
    def load_for_ocr(self, path: Path) -> Image.Image:
        """Return an EXIF-oriented, RGB-converted, optionally resized,
        denoised and contrast-normalised image ready for OCR.
        """

    @abstractmethod
    def load_for_emotion(self, path: Path) -> Image.Image:
        """Return an EXIF-oriented, RGB-converted image for face/emotion
        detection.  Let the HuggingFace feature extractor handle final
        normalisation.
        """
