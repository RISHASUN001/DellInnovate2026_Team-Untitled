"""
EmotionPort — abstract interface for facial emotion detection.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from PIL import Image

from domain.entities import EmotionResult


class EmotionPort(ABC):
    """Detect face and classify facial emotion from a PIL image."""

    @abstractmethod
    def detect(self, image: Image.Image) -> EmotionResult:
        """Run face detection + emotion classification on *image*.

        When no face is found, return an ``EmotionResult`` with
        ``face_detected_bool=False`` and empty label/zero score.
        Must not raise on images without faces.
        """
