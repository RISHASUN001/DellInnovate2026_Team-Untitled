"""
Application use cases.

Two use cases are exposed:

ProcessSingleImage
    Executes both pipelines (OCR → sentiment, face → emotion) for a single
    ``ImageJob``.  Never raises — errors are captured in the returned
    ``ImageRecord``.

RunBatchProcessing
    Discovers all images under an input folder, builds ``ImageJob``s, runs
    ``ProcessSingleImage`` for each, persists the aggregated results via the
    storage port, and returns a ``BatchRunSummary``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from application.filename_parser import discover_images, parse_image_filename
from config.settings import settings
from domain.entities import ImageJob, ImageRecord
from ports.emotion_port import EmotionPort
from adapters.smolvlm_adapter import SmolVLMAdapter
from ports.preprocessing_port import PreprocessingPort
from ports.sentiment_port import SentimentPort
from ports.storage_port import StoragePort

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Summary DTO
# ---------------------------------------------------------------------------


@dataclass
class BatchRunSummary:
    """Concise statistics returned after a full batch run."""

    total_images: int = 0
    ocr_detections: int = 0
    sentiment_inferences: int = 0
    face_detections: int = 0
    ocr_failures: int = 0
    emotion_failures: int = 0
    ocr_sentiment_output: Optional[Path] = None
    face_emotion_output: Optional[Path] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None

    def log_summary(self) -> None:
        elapsed = (
            (self.finished_at - self.started_at).total_seconds()
            if self.finished_at
            else None
        )
        logger.info(
            "\n"
            "========== BATCH RUN SUMMARY ==========\n"
            "  Images scanned      : %d\n"
            "  OCR detections      : %d\n"
            "  Sentiment inferences: %d\n"
            "  Face detections     : %d\n"
            "  OCR/pipeline errors : %d\n"
            "  Emotion errors      : %d\n"
            "  OCR output          : %s\n"
            "  Emotion output      : %s\n"
            "  Elapsed (s)         : %s\n"
            "========================================",
            self.total_images,
            self.ocr_detections,
            self.sentiment_inferences,
            self.face_detections,
            self.ocr_failures,
            self.emotion_failures,
            self.ocr_sentiment_output,
            self.face_emotion_output,
            f"{elapsed:.1f}" if elapsed is not None else "n/a",
        )


# ---------------------------------------------------------------------------
# Use case: ProcessSingleImage
# ---------------------------------------------------------------------------



class ProcessSingleImage:
    """Orchestrates both pipelines for one image, using SmolVLM for vision-language tasks."""

    def __init__(
        self,
        preprocessor: PreprocessingPort,
        smolvlm: SmolVLMAdapter,
        sentiment: SentimentPort,
        emotion: EmotionPort,
    ) -> None:
        self._preprocessor = preprocessor
        self._smolvlm = smolvlm
        self._sentiment = sentiment
        self._emotion = emotion

    # ------------------------------------------------------------------


    def execute(self, job: ImageJob) -> ImageRecord:
        """Run both pipelines and return an ``ImageRecord``.

        Failures in either pipeline are recorded in the record's error
        fields; the other pipeline continues regardless.
        """
        record = ImageRecord(job=job, processed_at=datetime.utcnow())

        # ---- Pipeline A: Vision-Language (SmolVLM) → Sentiment ---------
        try:
            # Use SmolVLM to describe the image and extract text
            prompt_text = "Extract all visible text from this image."
            extracted_text = self._smolvlm.describe_images([str(job.image_path)], prompt_text)
            if extracted_text:
                from domain.entities import OcrResult
                ocr_result = OcrResult(
                    ocr_text_raw=extracted_text,
                    ocr_text_clean=extracted_text.strip(),
                    ocr_char_count=len(extracted_text),
                    ocr_word_count=len(extracted_text.split()),
                    ocr_detected_bool=bool(extracted_text.strip()),
                )
                record.ocr_result = ocr_result
                record.sentiment_result = self._sentiment.analyze(ocr_result.ocr_text_clean)
            else:
                from domain.entities import OcrResult
                record.ocr_result = OcrResult(
                    ocr_text_raw="",
                    ocr_text_clean="",
                    ocr_char_count=0,
                    ocr_word_count=0,
                    ocr_detected_bool=False,
                )
        except Exception as exc:  # noqa: BLE001
            msg = f"Vision-language/sentiment pipeline error: {exc}"
            logger.error("[%s] %s", job.image_path.name, msg)
            record.error_ocr = msg

        # ---- Pipeline B: Face → Emotion ---------------------------------
        try:
            emotion_image = self._preprocessor.load_for_emotion(job.image_path)
            record.emotion_result = self._emotion.detect(emotion_image)
        except Exception as exc:  # noqa: BLE001
            msg = f"Emotion pipeline error: {exc}"
            logger.error("[%s] %s", job.image_path.name, msg)
            record.error_emotion = msg

        return record


# ---------------------------------------------------------------------------
# Use case: RunBatchProcessing
# ---------------------------------------------------------------------------


class RunBatchProcessing:
    """Discover images → build jobs → process → persist results."""

    def __init__(
        self,
        process_single: ProcessSingleImage,
        storage: StoragePort,
    ) -> None:
        self._process_single = process_single
        self._storage = storage

    # ------------------------------------------------------------------

    def execute(
        self,
        input_folder: Optional[Path] = None,
        overwrite: bool = False,
        max_images: int = 0,
    ) -> BatchRunSummary:
        folder = input_folder or settings.input_folder
        cap = max_images if max_images > 0 else settings.max_images

        logger.info("Scanning '%s' for images…", folder)
        all_paths = discover_images(folder)
        logger.info("Found %d image files.", len(all_paths))

        # Build jobs — skip files that don't match naming convention
        jobs: List[ImageJob] = []
        skipped = 0
        for path in all_paths:
            meta = parse_image_filename(path)
            if meta is None:
                logger.debug("Skipping '%s' — filename does not match convention.", path.name)
                skipped += 1
                continue
            jobs.append(ImageJob(image_path=path, metadata=meta))

        if skipped:
            logger.warning("%d files skipped (did not match naming convention).", skipped)

        if cap and len(jobs) > cap:
            logger.info("Capping to %d images (max_images=%d).", cap, cap)
            jobs = jobs[:cap]

        summary = BatchRunSummary(total_images=len(jobs))

        # ---- Process each job -------------------------------------------
        records: List[ImageRecord] = []
        for idx, job in enumerate(jobs, 1):
            logger.info(
                "[%d/%d] Processing %s …", idx, len(jobs), job.image_path.name
            )
            rec = self._process_single.execute(job)
            records.append(rec)

            # Tally stats
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

        # ---- Persist -------------------------------------------------------
        summary.ocr_sentiment_output = self._storage.save_ocr_sentiment(
            records, overwrite=overwrite
        )
        summary.face_emotion_output = self._storage.save_emotion(
            records, overwrite=overwrite
        )

        summary.finished_at = datetime.utcnow()
        summary.log_summary()
        return summary
