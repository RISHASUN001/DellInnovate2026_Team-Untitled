"""
SentimentPort — abstract interface for text sentiment analysis.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from domain.entities import SentimentResult


class SentimentPort(ABC):
    """Infer sentiment label + confidence from a text string."""

    @abstractmethod
    def analyze(self, text: str) -> SentimentResult:
        """Analyse *text* and return a sentiment result.

        Implementations must never raise on empty strings — return a
        ``SentimentResult(label="NEUTRAL", score=0.0)`` fallback.
        """
