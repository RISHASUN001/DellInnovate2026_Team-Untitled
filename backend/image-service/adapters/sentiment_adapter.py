"""
HuggingFaceSentimentAdapter — concrete implementation of SentimentPort.

Model: cardiffnlp/twitter-roberta-base-sentiment-latest

The transformers ``pipeline`` is initialised once and cached; all subsequent
calls reuse the warm model.  Label names are post-processed to a consistent
upper-case form (POSITIVE / NEGATIVE / NEUTRAL).
"""

from __future__ import annotations

import logging

from config.settings import settings
from domain.entities import SentimentResult
from ports.sentiment_port import SentimentPort

logger = logging.getLogger(__name__)

# Normalise the raw HuggingFace label to a clean common form
_LABEL_MAP: dict[str, str] = {
    "positive": "POSITIVE",
    "negative": "NEGATIVE",
    "neutral": "NEUTRAL",
    # model-specific aliases ↓
    "label_0": "NEGATIVE",
    "label_1": "NEUTRAL",
    "label_2": "POSITIVE",
}


def _normalise_label(raw: str) -> str:
    return _LABEL_MAP.get(raw.lower(), raw.upper())


class HuggingFaceSentimentAdapter(SentimentPort):
    """Sentiment inference using cardiffnlp/twitter-roberta-base-sentiment-latest."""

    def __init__(self) -> None:
        # Lazy import — deferred to avoid slow transformers scan at module load
        from transformers import pipeline  # noqa: PLC0415

        model_name = settings.sentiment_model
        device_id = 0 if settings.device in ("cuda", "mps") else -1
        logger.info("Loading sentiment model '%s' on device_id=%d…", model_name, device_id)
        self._pipe = pipeline(
            "text-classification",
            model=model_name,
            tokenizer=model_name,
            device=device_id,
            top_k=1,
        )
        logger.info("Sentiment model ready.")

    # ------------------------------------------------------------------

    def analyze(self, text: str) -> SentimentResult:
        if not text or not text.strip():
            return SentimentResult(sentiment_label="NEUTRAL", sentiment_score=0.0)

        try:
            # pipeline returns [[{label, score}]] when top_k=1  (lazy-imported pipe)
            results = self._pipe(text, truncation=True, max_length=512)
            top = results[0][0] if results and results[0] else {}
            raw_label = top.get("label", "NEUTRAL")
            score = float(top.get("score", 0.0))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Sentiment inference failed: %s", exc)
            return SentimentResult(sentiment_label="NEUTRAL", sentiment_score=0.0)

        return SentimentResult(
            sentiment_label=_normalise_label(raw_label),
            sentiment_score=score,
        )
