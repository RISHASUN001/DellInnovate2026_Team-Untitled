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
import os
from datetime import datetime
from pathlib import Path
from typing import List, Set, Dict

from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure

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
    """CSV-backed storage adapter with MongoDB sync."""

    def __init__(self, output_folder: Path | None = None) -> None:
        self._output_folder: Path = output_folder or settings.output_folder
        self._output_folder.mkdir(parents=True, exist_ok=True)
        self._init_mongodb()

    # ------------------------------------------------------------------
    # MongoDB Integration
    # ------------------------------------------------------------------

    def _init_mongodb(self) -> None:
        """Initialize MongoDB connection for instagram_scraper.image_analysis collection."""
        self.mongodb_client = None
        self.mongodb_collection = None
        
        try:
            mongodb_uri = settings.mongodb_uri
            if not mongodb_uri:
                logger.warning("MONGODB_URI not set - MongoDB sync disabled")
                return
            
            # Connect to instagram_scraper database (from settings)
            self.mongodb_client = MongoClient(mongodb_uri)
            db_name = settings.mongodb_db_name or "instagram_scraper"
            db = self.mongodb_client[db_name]
            self.mongodb_collection = db["image_analysis"]
            
            # Create index on image_path for efficient lookups
            self.mongodb_collection.create_index([("image_path", ASCENDING)], unique=True)
            
            logger.info(f"✓ MongoDB sync enabled: {db_name}.image_analysis")
        except ConnectionFailure as e:
            logger.error(f"MongoDB connection failed: {e} - sync disabled")
            self.mongodb_client = None
            self.mongodb_collection = None
        except Exception as e:
            logger.error(f"MongoDB initialization error: {e} - sync disabled")
            self.mongodb_client = None
            self.mongodb_collection = None

    def _get_existing_records(self, image_paths: List[str]) -> Set[str]:
        """Get set of image_paths that already exist in MongoDB."""
        if self.mongodb_collection is None:
            return set()
        
        try:
            # Query only image_path field for efficiency
            existing = self.mongodb_collection.find(
                {"image_path": {"$in": image_paths}},
                {"image_path": 1, "_id": 0}
            )
            return {doc["image_path"] for doc in existing}
        except Exception as e:
            logger.error(f"Error checking existing records: {e}")
            return set()

    def _sync_to_mongodb(self, records: List[ImageRecord]) -> None:
        """Sync new/changed records to MongoDB image_analysis collection."""
        if self.mongodb_collection is None:
            logger.debug("MongoDB not configured - skipping sync")
            return
        
        try:
            # Get existing records to determine what needs syncing
            image_paths = [rec.image_path_str for rec in records]
            existing_paths = self._get_existing_records(image_paths)
            
            # Filter to only new records (not already in DB)
            new_records = [rec for rec in records if rec.image_path_str not in existing_paths]
            
            if not new_records:
                logger.info(f"All {len(records)} records already in MongoDB - skipping sync")
                return
            
            # Prepare documents for MongoDB
            documents = []
            for rec in new_records:
                ocr = rec.ocr_result
                sentiment = rec.sentiment_result
                emotion = rec.emotion_result
                
                doc = {
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
                    "sentiment_score": float(sentiment.sentiment_score) if sentiment and sentiment.sentiment_score else 0.0,
                    # VLM Scene Description
                    "scene_description": rec.image_description or "",
                    # VLM Emotion Analysis
                    "vlm_emotion_description": rec.vlm_emotion_description or "",
                    # Face Emotion Detection
                    "face_detected_bool": emotion.face_detected_bool if emotion else False,
                    "face_emotion_label": emotion.emotion_label if emotion else "",
                    "face_emotion_score": float(emotion.emotion_score) if emotion and emotion.emotion_score else 0.0,
                    # Metadata
                    "processed_at": rec.processed_at.isoformat(),
                    "synced_at": datetime.utcnow().isoformat(),
                }
                documents.append(doc)
            
            # Bulk upsert to MongoDB
            if documents:
                from pymongo import UpdateOne
                operations = [
                    UpdateOne(
                        {"image_path": doc["image_path"]},
                        {"$set": doc},
                        upsert=True
                    )
                    for doc in documents
                ]
                result = self.mongodb_collection.bulk_write(operations, ordered=False)
                logger.info(
                    f"✓ MongoDB sync: {result.upserted_count} inserted, "
                    f"{result.modified_count} updated (skipped {len(existing_paths)} existing)"
                )
        except Exception as e:
            logger.error(f"MongoDB sync failed: {e}", exc_info=True)

    def populate_from_csv(self, csv_path: str | Path) -> Dict[str, int]:
        """
        Populate MongoDB from an existing vlm_complete_analysis.csv file.
        
        Args:
            csv_path: Path to the CSV file to import
            
        Returns:
            Dict with counts of inserted/updated/skipped records
        """
        if self.mongodb_collection is None:
            logger.error("MongoDB not configured - cannot populate from CSV")
            return {"error": 1, "inserted": 0, "updated": 0, "skipped": 0}
        
        csv_path = Path(csv_path)
        if not csv_path.exists():
            logger.error(f"CSV file not found: {csv_path}")
            return {"error": 1, "inserted": 0, "updated": 0, "skipped": 0}
        
        try:
            from pymongo import UpdateOne
            
            documents = []
            with csv_path.open("r", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                
                for row in reader:
                    # Parse CSV row into MongoDB document format
                    doc = {
                        "image_path": row.get("image_path", ""),
                        "ig_handle": row.get("ig_handle", ""),
                        "post_date": row.get("post_date", ""),
                        "image_index": int(row.get("image_index", 0)),
                        # OCR & Text
                        "ocr_text_raw": row.get("ocr_text_raw", ""),
                        "ocr_text_clean": row.get("ocr_text_clean", ""),
                        "ocr_detected_bool": row.get("ocr_detected_bool", "false").lower() == "true",
                        # Sentiment
                        "sentiment_label": row.get("sentiment_label", ""),
                        "sentiment_score": float(row.get("sentiment_score", 0.0)) if row.get("sentiment_score") else 0.0,
                        # VLM Scene Description
                        "scene_description": row.get("scene_description", ""),
                        # VLM Emotion Analysis
                        "vlm_emotion_description": row.get("vlm_emotion_description", ""),
                        # Face Emotion Detection
                        "face_detected_bool": row.get("face_detected_bool", "false").lower() == "true",
                        "face_emotion_label": row.get("face_emotion_label", ""),
                        "face_emotion_score": float(row.get("face_emotion_score", 0.0)) if row.get("face_emotion_score") else 0.0,
                        # Metadata
                        "processed_at": row.get("processed_at", ""),
                        "synced_at": datetime.utcnow().isoformat(),
                        "imported_from_csv": True,
                    }
                    documents.append(doc)
            
            if not documents:
                logger.warning(f"No records found in CSV: {csv_path}")
                return {"error": 0, "inserted": 0, "updated": 0, "skipped": 0}
            
            # Check which records already exist
            image_paths = [doc["image_path"] for doc in documents]
            existing_paths = self._get_existing_records(image_paths)
            
            # Bulk upsert all documents
            operations = [
                UpdateOne(
                    {"image_path": doc["image_path"]},
                    {"$set": doc},
                    upsert=True
                )
                for doc in documents
            ]
            
            result = self.mongodb_collection.bulk_write(operations, ordered=False)
            
            stats = {
                "error": 0,
                "inserted": result.upserted_count,
                "updated": result.modified_count,
                "skipped": len(existing_paths) - result.modified_count,
                "total": len(documents),
            }
            
            logger.info(
                f"✓ CSV import complete: {stats['inserted']} inserted, "
                f"{stats['updated']} updated, {stats['skipped']} skipped "
                f"(total: {stats['total']} records from {csv_path})"
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to populate MongoDB from CSV: {e}", exc_info=True)
            return {"error": 1, "inserted": 0, "updated": 0, "skipped": 0}

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
        
        # Sync new records to MongoDB
        self._sync_to_mongodb(records)
        
        return out_path
