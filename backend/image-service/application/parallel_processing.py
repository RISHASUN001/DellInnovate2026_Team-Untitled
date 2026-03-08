"""
Parallel and batch processing optimizations for image-service.

This module provides:
1. Concurrent image processing using asyncio
2. Batch inference support
3. Progress tracking
4. Memory-efficient streaming
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from application.use_cases import BatchRunSummary, ProcessSingleImage
from config.settings import settings
from domain.entities import ImageJob, ImageRecord
from ports.storage_port import StoragePort

logger = logging.getLogger(__name__)


@dataclass
class ParallelProcessingConfig:
    """Configuration for parallel processing."""
    
    max_workers: int = 4  # Number of parallel workers
    batch_size: int = 8  # Images to process in one batch
    enable_progress: bool = True  # Log progress updates
    max_memory_mb: int = 4096  # Max memory to use (approx)


class ParallelBatchProcessing:
    """Process images in parallel with batching support."""

    def __init__(
        self,
        process_single: ProcessSingleImage,
        storage: StoragePort,
        config: Optional[ParallelProcessingConfig] = None,
    ) -> None:
        self._process_single = process_single
        self._storage = storage
        self._config = config or ParallelProcessingConfig()
        
        logger.info(
            "ParallelBatchProcessing initialized: workers=%d, batch=%d",
            self._config.max_workers,
            self._config.batch_size,
        )

    def execute_parallel(
        self,
        jobs: List[ImageJob],
        overwrite: bool = False,
    ) -> BatchRunSummary:
        """Execute jobs in parallel using ThreadPoolExecutor."""
        summary = BatchRunSummary(
            total_images=len(jobs),
            started_at=datetime.utcnow(),
        )
        
        if not jobs:
            summary.finished_at = datetime.utcnow()
            return summary

        records: List[ImageRecord] = []
        completed = 0
        
        logger.info("Processing %d images with %d workers...", len(jobs), self._config.max_workers)
        
        with ThreadPoolExecutor(max_workers=self._config.max_workers) as executor:
            # Submit all jobs
            future_to_job = {
                executor.submit(self._process_single.execute, job): job
                for job in jobs
            }
            
            # Process results as they complete
            for future in as_completed(future_to_job):
                job = future_to_job[future]
                try:
                    rec = future.result()
                    records.append(rec)
                    completed += 1
                    
                    # Update stats
                    self._update_summary(summary, rec)
                    
                    # Progress logging
                    if self._config.enable_progress and completed % 10 == 0:
                        elapsed = (datetime.utcnow() - summary.started_at).total_seconds()
                        rate = completed / elapsed if elapsed > 0 else 0
                        eta = (len(jobs) - completed) / rate if rate > 0 else 0
                        logger.info(
                            "Progress: %d/%d (%.1f%%) | Rate: %.1f img/s | ETA: %.0fs",
                            completed, len(jobs), 100 * completed / len(jobs), rate, eta
                        )
                
                except Exception as exc:
                    logger.error("Failed to process %s: %s", job.image_path.name, exc)
                    summary.ocr_failures += 1
                    summary.emotion_failures += 1

        # Persist results
        logger.info("Persisting %d records to storage...", len(records))
        summary.ocr_sentiment_output = self._storage.save_ocr_sentiment(records, overwrite=overwrite)
        summary.face_emotion_output = self._storage.save_emotion(records, overwrite=overwrite)
        
        summary.finished_at = datetime.utcnow()
        summary.log_summary()
        
        return summary

    def execute_batched(
        self,
        jobs: List[ImageJob],
        overwrite: bool = False,
    ) -> BatchRunSummary:
        """Execute jobs in batches for better memory efficiency."""
        summary = BatchRunSummary(
            total_images=len(jobs),
            started_at=datetime.utcnow(),
        )
        
        if not jobs:
            summary.finished_at = datetime.utcnow()
            return summary

        all_records: List[ImageRecord] = []
        batch_size = self._config.batch_size
        num_batches = (len(jobs) + batch_size - 1) // batch_size
        
        logger.info(
            "Processing %d images in %d batches (size=%d)...",
            len(jobs), num_batches, batch_size
        )
        
        for batch_idx in range(num_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(jobs))
            batch_jobs = jobs[start_idx:end_idx]
            
            logger.info("Processing batch %d/%d (%d images)...", batch_idx + 1, num_batches, len(batch_jobs))
            
            # Process batch in parallel
            batch_records = []
            with ThreadPoolExecutor(max_workers=self._config.max_workers) as executor:
                futures = [executor.submit(self._process_single.execute, job) for job in batch_jobs]
                
                for future in as_completed(futures):
                    try:
                        rec = future.result()
                        batch_records.append(rec)
                        self._update_summary(summary, rec)
                    except Exception as exc:
                        logger.error("Batch processing error: %s", exc)
                        summary.ocr_failures += 1
                        summary.emotion_failures += 1
            
            all_records.extend(batch_records)
            
            # Progress update
            completed = end_idx
            elapsed = (datetime.utcnow() - summary.started_at).total_seconds()
            rate = completed / elapsed if elapsed > 0 else 0
            eta = (len(jobs) - completed) / rate if rate > 0 else 0
            
            logger.info(
                "Batch %d/%d complete | Overall: %d/%d (%.1f%%) | Rate: %.1f img/s | ETA: %.0fs",
                batch_idx + 1, num_batches, completed, len(jobs),
                100 * completed / len(jobs), rate, eta
            )

        # Persist all results
        logger.info("Persisting %d records to storage...", len(all_records))
        summary.ocr_sentiment_output = self._storage.save_ocr_sentiment(all_records, overwrite=overwrite)
        summary.face_emotion_output = self._storage.save_emotion(all_records, overwrite=overwrite)
        
        summary.finished_at = datetime.utcnow()
        summary.log_summary()
        
        return summary

    def _update_summary(self, summary: BatchRunSummary, rec: ImageRecord) -> None:
        """Update summary statistics from a processed record."""
        if rec.ocr_result and rec.ocr_result.ocr_detected_bool:
            summary.ocr_detections += 1
        if rec.sentiment_result:
            summary.sentiment_inferences += 1
        if rec.emotion_result and rec.emotion_result.face_detected_bool:
            summary.face_detections += 1
        if rec.error_ocr:
            summary.ocr_failures += 1
        if rec.error_emotion:
            summary.emotion_failures += 1


class StreamingBatchProcessing:
    """Memory-efficient streaming processing for very large batches."""

    def __init__(
        self,
        process_single: ProcessSingleImage,
        storage: StoragePort,
        chunk_size: int = 50,
        max_workers: int = 4,
    ) -> None:
        self._process_single = process_single
        self._storage = storage
        self._chunk_size = chunk_size
        self._max_workers = max_workers
        
        logger.info(
            "StreamingBatchProcessing initialized: chunk=%d, workers=%d",
            chunk_size, max_workers
        )

    def execute_streaming(
        self,
        jobs: List[ImageJob],
        overwrite: bool = False,
    ) -> BatchRunSummary:
        """Process and persist in chunks to minimize memory usage."""
        summary = BatchRunSummary(
            total_images=len(jobs),
            started_at=datetime.utcnow(),
        )
        
        if not jobs:
            summary.finished_at = datetime.utcnow()
            return summary

        num_chunks = (len(jobs) + self._chunk_size - 1) // self._chunk_size
        
        logger.info(
            "Streaming processing: %d images in %d chunks (size=%d)...",
            len(jobs), num_chunks, self._chunk_size
        )
        
        for chunk_idx in range(num_chunks):
            start_idx = chunk_idx * self._chunk_size
            end_idx = min(start_idx + self._chunk_size, len(jobs))
            chunk_jobs = jobs[start_idx:end_idx]
            
            logger.info("Processing chunk %d/%d (%d images)...", chunk_idx + 1, num_chunks, len(chunk_jobs))
            
            # Process chunk
            chunk_records = []
            with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
                futures = [executor.submit(self._process_single.execute, job) for job in chunk_jobs]
                
                for future in as_completed(futures):
                    try:
                        rec = future.result()
                        chunk_records.append(rec)
                        
                        # Update stats
                        if rec.ocr_result and rec.ocr_result.ocr_detected_bool:
                            summary.ocr_detections += 1
                        if rec.sentiment_result:
                            summary.sentiment_inferences += 1
                        if rec.emotion_result and rec.emotion_result.face_detected_bool:
                            summary.face_detections += 1
                        if rec.error_ocr:
                            summary.ocr_failures += 1
                        if rec.error_emotion:
                            summary.emotion_failures += 1
                    
                    except Exception as exc:
                        logger.error("Chunk processing error: %s", exc)
                        summary.ocr_failures += 1
                        summary.emotion_failures += 1
            
            # Immediately persist this chunk (stream to disk)
            self._storage.save_ocr_sentiment(chunk_records, overwrite=(overwrite and chunk_idx == 0))
            self._storage.save_emotion(chunk_records, overwrite=(overwrite and chunk_idx == 0))
            
            # Progress
            completed = end_idx
            elapsed = (datetime.utcnow() - summary.started_at).total_seconds()
            rate = completed / elapsed if elapsed > 0 else 0
            eta = (len(jobs) - completed) / rate if rate > 0 else 0
            
            logger.info(
                "Chunk %d/%d persisted | Overall: %d/%d (%.1f%%) | Rate: %.1f img/s | ETA: %.0fs",
                chunk_idx + 1, num_chunks, completed, len(jobs),
                100 * completed / len(jobs), rate, eta
            )

        summary.finished_at = datetime.utcnow()
        summary.log_summary()
        
        return summary
