"""
MongoDBStorageAdapter — concrete implementation of StoragePort.

Writes image analysis results to MongoDB collection.
Each record contains OCR, sentiment, and emotion analysis data.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time
from typing import List

from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure, OperationFailure

from config.settings import settings
from domain.entities import ImageRecord
from ports.storage_port import StoragePort

logger = logging.getLogger(__name__)


def _to_bson_datetime(value: date | datetime) -> datetime:
    """Convert date/datetime to a BSON-encodable datetime."""
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, time.min)


class MongoDBStorageAdapter(StoragePort):
    """MongoDB-backed storage adapter."""

    def __init__(self) -> None:
        """Initialize MongoDB connection."""
        try:
            self.client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
            # Test connection
            self.client.admin.command('ping')
            logger.info("Successfully connected to MongoDB")
            
            self.db = self.client[settings.mongodb_db_name]
            self.collection = self.db[settings.mongodb_collection_name]
            
            # Create indexes for better query performance
            self.collection.create_index([("ig_handle", ASCENDING)])
            self.collection.create_index([("post_date", ASCENDING)])
            self.collection.create_index([("processed_at", ASCENDING)])
            
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
        except Exception as e:
            logger.error(f"Error initializing MongoDB adapter: {e}")
            raise

    def save_ocr_sentiment(
        self, records: List[ImageRecord], overwrite: bool = False
    ) -> str:
        """Save OCR and sentiment results to MongoDB."""
        if not records:
            logger.warning("No records to save")
            return "No records saved"

        documents = []
        for rec in records:
            ocr = rec.ocr_result
            sentiment = rec.sentiment_result
            
            doc = {
                "image_path": rec.image_path_str,
                "ig_handle": rec.ig_handle,
                "post_date": _to_bson_datetime(rec.post_date),
                "image_index": rec.image_index,
                "analysis_type": "ocr_sentiment",
                "ocr_data": {
                    "text_raw": ocr.ocr_text_raw if ocr else "",
                    "text_clean": ocr.ocr_text_clean if ocr else "",
                    "char_count": ocr.ocr_char_count if ocr else 0,
                    "word_count": ocr.ocr_word_count if ocr else 0,
                    "detected": ocr.ocr_detected_bool if ocr else False,
                },
                "sentiment_data": {
                    "label": sentiment.sentiment_label if sentiment else "",
                    "score": sentiment.sentiment_score if sentiment else 0.0,
                } if sentiment else None,
                "processed_at": rec.processed_at,
                "errors": rec.error_ocr if rec.error_ocr else None,
            }
            documents.append(doc)

        try:
            if overwrite:
                # Delete existing records for these images
                image_paths = [rec.image_path_str for rec in records]
                self.collection.delete_many({
                    "image_path": {"$in": image_paths},
                    "analysis_type": "ocr_sentiment"
                })
            
            result = self.collection.insert_many(documents)
            logger.info(f"Saved {len(result.inserted_ids)} OCR/sentiment records to MongoDB")
            return f"Saved {len(result.inserted_ids)} records"
        except OperationFailure as e:
            logger.error(f"Failed to save OCR/sentiment data to MongoDB: {e}")
            raise

    def save_emotion(
        self, records: List[ImageRecord], overwrite: bool = False
    ) -> str:
        """Save emotion detection results to MongoDB."""
        if not records:
            logger.warning("No records to save")
            return "No records saved"

        documents = []
        for rec in records:
            em = rec.emotion_result
            
            doc = {
                "image_path": rec.image_path_str,
                "ig_handle": rec.ig_handle,
                "post_date": _to_bson_datetime(rec.post_date),
                "image_index": rec.image_index,
                "analysis_type": "emotion",
                "image_description": rec.image_description or "",
                "emotion_data": {
                    "face_detected": em.face_detected_bool if em else False,
                    "emotion_label": em.emotion_label if em else "",
                    "emotion_score": em.emotion_score if em else 0.0,
                    "model_name": em.model_name if em else "",
                },
                "vlm_analysis": {
                    "emotion_description": rec.vlm_emotion_description or "",
                    "fused_assessment": rec.fused_emotion_assessment or "",
                },
                "processed_at": rec.processed_at,
                "errors": rec.error_emotion if rec.error_emotion else None,
            }
            documents.append(doc)

        try:
            if overwrite:
                # Delete existing records for these images
                image_paths = [rec.image_path_str for rec in records]
                self.collection.delete_many({
                    "image_path": {"$in": image_paths},
                    "analysis_type": "emotion"
                })
            
            result = self.collection.insert_many(documents)
            logger.info(f"Saved {len(result.inserted_ids)} emotion records to MongoDB")
            return f"Saved {len(result.inserted_ids)} records"
        except OperationFailure as e:
            logger.error(f"Failed to save emotion data to MongoDB: {e}")
            raise

    def __del__(self):
        """Close MongoDB connection on cleanup."""
        try:
            if hasattr(self, "client"):
                self.client.close()
        except Exception:
            # Interpreter shutdown can invalidate imports; ignore cleanup errors.
            pass
