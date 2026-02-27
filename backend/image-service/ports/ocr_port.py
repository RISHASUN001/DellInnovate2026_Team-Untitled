"""
OcrPort — abstract interface for optical character recognition.

The application layer depends solely on this port, making it trivial to
swap out easyocr for tesseract, cloud Vision APIs, etc.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from PIL import Image

from domain.entities import OcrResult


class OcrPort(ABC):
    """Extract text from a PIL image."""

    @abstractmethod
    def extract(self, image: Image.Image) -> OcrResult:
        """Run OCR on *image* and return a structured result.

        Must not raise on empty images — return a result with
        ``ocr_detected_bool=False`` instead.
        """
