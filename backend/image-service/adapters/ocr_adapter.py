"""
EasyOcrAdapter — concrete implementation of OcrPort using easyocr.

The adapter is responsible for:
  - Running easyocr on the supplied PIL image
  - Cleaning / normalising the extracted text
  - Computing basic text statistics
  - Deciding whether enough text was found (ocr_detected_bool)

The OCR reader is initialised *once* and cached inside the adapter instance
(warm-loading) so subsequent calls skip model re-loading.

Heavy imports (easyocr, numpy) are deferred to __init__ so the FastAPI app
can be imported quickly by uvicorn before models are loaded.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import TYPE_CHECKING

from PIL import Image

from config.settings import settings
from domain.entities import OcrResult
from ports.ocr_port import OcrPort

logger = logging.getLogger(__name__)


# Tokens that are ≥ this fraction non-alphanumeric are considered noise
_MAX_NONALPHA_RATIO: float = 0.5
# Tokens shorter than this are dropped (single stray chars, punctuation)
_MIN_TOKEN_LEN: int = 2
# Minimum OCR confidence to keep a detection [0–1]
_MIN_CONFIDENCE: float = 0.4


def _is_clean_token(token: str) -> bool:
    """Return True if *token* looks like real text rather than OCR garbage."""
    if len(token) < _MIN_TOKEN_LEN:
        return False
    alpha_count = sum(1 for ch in token if ch.isalpha())
    # Token must be at least 50 % alphabetic after stripping surrounding punct
    if len(token) > 0 and alpha_count / len(token) < (1 - _MAX_NONALPHA_RATIO):
        return False
    return True


def _clean_text(raw: str) -> str:
    """Normalise unicode, strip control chars, collapse whitespace, remove noise tokens."""
    text = unicodedata.normalize("NFKC", raw)
    # Remove non-printable characters
    text = "".join(ch for ch in text if ch.isprintable() or ch in ("\n", "\t"))
    # Collapse runs of whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Filter individual tokens that look like OCR noise
    tokens = text.split()
    tokens = [t for t in tokens if _is_clean_token(t)]
    return " ".join(tokens)


class EasyOcrAdapter(OcrPort):
    """OCR adapter backed by EasyOCR."""

    def __init__(self) -> None:
        # Lazy import — keeps module-level import fast for uvicorn startup
        import easyocr  # noqa: PLC0415
        import numpy as _np  # noqa: PLC0415
        self._np = _np

        lang = settings.ocr_language
        gpu = settings.device not in ("cpu",)
        logger.info("Initialising EasyOCR reader (lang=%s, gpu=%s)…", lang, gpu)
        self._reader = easyocr.Reader([lang], gpu=gpu, verbose=False)
        logger.info("EasyOCR ready.")

    # ------------------------------------------------------------------

    def extract(self, image: Image.Image) -> OcrResult:
        try:
            # Upscale small images — EasyOCR accuracy improves significantly on
            # images wider than ~800 px; on small crops we scale 2× first.
            w, h = image.size
            if max(w, h) < 800:
                scale = 800 / max(w, h)
                image = image.resize(
                    (int(w * scale), int(h * scale)), Image.LANCZOS
                )

            img_array = self._np.array(image)
            # detail=1 returns (bbox, text, confidence) tuples; we filter by
            # confidence so garbled low-quality detections are excluded.
            detections = self._reader.readtext(img_array, detail=1,
                                               paragraph=False)
            kept = [
                text
                for (_bbox, text, conf) in detections
                if conf >= _MIN_CONFIDENCE and text.strip()
            ]
            raw_text = " ".join(kept)
        except Exception as exc:  # noqa: BLE001
            logger.warning("EasyOCR extraction failed: %s", exc)
            raw_text = ""

        clean_text = _clean_text(raw_text)
        char_count = len(clean_text)
        word_count = len(clean_text.split()) if clean_text else 0
        detected = char_count >= settings.ocr_min_chars

        return OcrResult(
            ocr_text_raw=raw_text,
            ocr_text_clean=clean_text,
            ocr_char_count=char_count,
            ocr_word_count=word_count,
            ocr_detected_bool=detected,
        )
