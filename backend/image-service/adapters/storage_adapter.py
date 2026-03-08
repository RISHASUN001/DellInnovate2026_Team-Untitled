"""
CsvStorageAdapter — concrete implementation of StoragePort.

Writes two CSV files under ``outputs/``:
  - ocr_sentiment_results.csv
  - face_emotion_results.csv

Columns are defined in the spec; rows are appended or overwritten based on
the *overwrite* flag.  Thread-safety is intentionally out of scope for this
single-process service.
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import List

from config.settings import settings
from domain.entities import ImageRecord
from ports.storage_port import StoragePort

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------
# Column specs
# -----------------------------------------------------------------------

OCR_SENTIMENT_COLUMNS = [
    "image_path",
    "ig_handle",
    "post_date",
    "image_index",
    "ocr_text_raw",
    "ocr_text_clean",
    "sentiment_label",
    "sentiment_score",
    "ocr_char_count",
    "ocr_word_count",
    "ocr_detected_bool",
    "processed_at",
]

FACE_EMOTION_COLUMNS = [
    "image_path",
    "ig_handle",
    "post_date",
    "image_index",
    "face_detected_bool",
    "emotion_label",
    "emotion_score",
    "model_name",
    "vlm_emotion_description",
    "fused_emotion_assessment",
    "processed_at",
]

# VLM Complete Analysis - includes all VLM outputs
VLM_COMPLETE_COLUMNS = [
    "image_path",
    "ig_handle",
    "post_date",
    "image_index",
    # OCR & Text
    "ocr_text_raw",
    "ocr_text_clean",
    "ocr_detected_bool",
    # Sentiment
    "sentiment_label",
    "sentiment_score",
    # VLM Scene Description
    "scene_description",
    # VLM Emotion Analysis
    "vlm_emotion_description",
    # Face Emotion Detection
    "face_detected_bool",
    "face_emotion_label",
    "face_emotion_score",
    # Metadata
    "processed_at",
]


class CsvStorageAdapter(StoragePort):
    """CSV-backed storage adapter."""

    def __init__(self, output_folder: Path | None = None) -> None:
        self._output_folder: Path = output_folder or settings.output_folder
        self._output_folder.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------

    def save_ocr_sentiment(
        self, records: List[ImageRecord], overwrite: bool = False
    ) -> Path:
        out_path = self._output_folder / "ocr_sentiment_results.csv"
        mode = "w" if overwrite or not out_path.exists() else "a"
        write_header = mode == "w"

        with out_path.open(mode, newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=OCR_SENTIMENT_COLUMNS)
            if write_header:
                writer.writeheader()

            for rec in records:
                ocr = rec.ocr_result
                sentiment = rec.sentiment_result
                row: dict = {
                    "image_path": rec.image_path_str,
                    "ig_handle": rec.ig_handle,
                    "post_date": rec.post_date.isoformat(),
                    "image_index": rec.image_index,
                    "ocr_text_raw": ocr.ocr_text_raw if ocr else "",
                    "ocr_text_clean": ocr.ocr_text_clean if ocr else "",
                    "sentiment_label": sentiment.sentiment_label if sentiment else "",
                    "sentiment_score": sentiment.sentiment_score if sentiment else "",
                    "ocr_char_count": ocr.ocr_char_count if ocr else 0,
                    "ocr_word_count": ocr.ocr_word_count if ocr else 0,
                    "ocr_detected_bool": ocr.ocr_detected_bool if ocr else False,
                    "processed_at": rec.processed_at.isoformat(),
                }
                writer.writerow(row)

        logger.info("OCR/sentiment results written to %s (%d rows)", out_path, len(records))
        return out_path

    # ------------------------------------------------------------------

    def save_emotion(
        self, records: List[ImageRecord], overwrite: bool = False
    ) -> Path:
        out_path = self._output_folder / "face_emotion_results.csv"
        mode = "w" if overwrite or not out_path.exists() else "a"
        write_header = mode == "w"

        with out_path.open(mode, newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=FACE_EMOTION_COLUMNS)
            if write_header:
                writer.writeheader()

            for rec in records:
                em = rec.emotion_result
                row: dict = {
                    "image_path": rec.image_path_str,
                    "ig_handle": rec.ig_handle,
                    "post_date": rec.post_date.isoformat(),
                    "image_index": rec.image_index,
                    "face_detected_bool": em.face_detected_bool if em else False,
                    "emotion_label": em.emotion_label if em else "",
                    "emotion_score": em.emotion_score if em else 0.0,
                    "model_name": em.model_name if em else "",
                    "vlm_emotion_description": rec.vlm_emotion_description or "",
                    "fused_emotion_assessment": rec.fused_emotion_assessment or "",
                    "processed_at": rec.processed_at.isoformat(),
                }
                writer.writerow(row)

        logger.info("Face/emotion results written to %s (%d rows)", out_path, len(records))
        return out_path

    # ------------------------------------------------------------------

    def save_vlm_complete(self, records: List[ImageRecord], overwrite: bool = False) -> Path:
        """Save complete VLM analysis results including OCR, sentiment, and emotion."""
        out_path = self._output_folder / "vlm_complete_analysis.csv"
        mode = "w" if overwrite or not out_path.exists() else "a"
        write_header = mode == "w"

        with out_path.open(mode, newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=VLM_COMPLETE_COLUMNS)
            if write_header:
                writer.writeheader()

            for rec in records:
                ocr = rec.ocr_result
                sentiment = rec.sentiment_result
                emotion = rec.emotion_result
                
                row: dict = {
                    "image_path": rec.image_path_str,
                    "ig_handle": rec.ig_handle,
                    "post_date": rec.post_date.isoformat(),
                    "image_index": rec.image_index,
                    # OCR & Text
                    "ocr_text_raw": ocr.ocr_text_raw if ocr else "",
                    "ocr_text_clean": ocr.ocr_text_clean if ocr else "",
                    "ocr_detected_bool": ocr.ocr_detected_bool if ocr else False,
                    # Sentiment
                    "sentiment_label": sentiment.sentiment_label if sentiment else "",
                    "sentiment_score": sentiment.sentiment_score if sentiment else "",
                    # VLM Scene Description
                    "scene_description": rec.image_description or "",
                    # VLM Emotion Analysis
                    "vlm_emotion_description": rec.vlm_emotion_description or "",
                    # Face Emotion Detection
                    "face_detected_bool": emotion.face_detected_bool if emotion else False,
                    "face_emotion_label": emotion.emotion_label if emotion else "",
                    "face_emotion_score": emotion.emotion_score if emotion else 0.0,
                    # Metadata
                    "processed_at": rec.processed_at.isoformat(),
                }
                writer.writerow(row)

        logger.info("Complete VLM analysis written to %s (%d rows)", out_path, len(records))
        return out_path
