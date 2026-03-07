"""
StoragePort — abstract interface for persisting pipeline results.

The application layer writes ``ImageRecord`` objects through this port;
the concrete adapter decides whether to use CSV, a database, S3, etc.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Union

from domain.entities import ImageRecord


class StoragePort(ABC):
    """Persist image-processing results."""

    @abstractmethod
    def save_ocr_sentiment(self, records: List[ImageRecord], overwrite: bool = False) -> Union[Path, str]:
        """Write OCR + sentiment results and return the output path or status message."""

    @abstractmethod
    def save_emotion(self, records: List[ImageRecord], overwrite: bool = False) -> Union[Path, str]:
        """Write face-emotion results and return the output path or status message."""
