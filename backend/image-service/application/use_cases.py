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
import re
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


def _normalize_vlm_output(text: str | None) -> str:
    if not text:
        return ""

    cleaned = text.strip()
    for prefix in ("Assistant:", "assistant:", "Answer:", "answer:"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
    return cleaned


def _is_none_output(text: str | None) -> bool:
    cleaned = _normalize_vlm_output(text)
    if not cleaned:
        return True

    compact = re.sub(r"[^A-Za-z0-9]+", "", cleaned).upper()
    return compact in {"NONE", "NOTEXT", "NOTEXTVISIBLE", "NA", "N/A"}


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
        """Run the full multi-stage emotional reasoning pipeline and return an ImageRecord."""
        import time
        pipeline_start = time.time()
        record = ImageRecord(job=job, processed_at=datetime.utcnow())

        # --- Preprocessing: Create optimized image file for VLM inference ---
        preprocess_start = time.time()
        logger.info("[%s] 🔄 Preprocessing image for VLM...", job.image_path.name)
        try:
            preprocessed_path = self._preprocessor.preprocess_and_save(job.image_path)
            preprocess_elapsed = time.time() - preprocess_start
            logger.info("[%s] ✅ Preprocessing completed (%.2fs) - Using: %s", 
                       job.image_path.name, preprocess_elapsed, preprocessed_path.name)
        except Exception as exc:
            preprocess_elapsed = time.time() - preprocess_start
            logger.error("[%s] ⚠️ Preprocessing failed (%.2fs), using original: %s", 
                        job.image_path.name, preprocess_elapsed, exc)
            preprocessed_path = job.image_path  # Fallback to original

        # --- 0. VLM Scene Description ---
        step_start = time.time()
        IMAGE_DESCRIPTION_PROMPT = """Describe this image focusing on visual mood:
- People: posture, facial expressions, gestures
- Colors: dominant tones (dark/bright, warm/cold)
- Lighting: shadows, brightness, contrast
- Composition: positioning, isolation, crowding
- Atmosphere indicators
2-3 sentences."""
        try:
            logger.info("[%s] Starting scene description (VLM inference)...", job.image_path.name)
            scene_desc = self._smolvlm.describe_images(
                [str(preprocessed_path)], IMAGE_DESCRIPTION_PROMPT.strip()
            )
            # Check if VLM returned None (API failure)
            if scene_desc is None:
                msg = "VLM API returned None (possible insufficient credits or API error)"
                logger.error("[%s] %s", job.image_path.name, msg)
                record.image_description = f"ERROR: {msg}"
            else:
                record.image_description = _normalize_vlm_output(scene_desc)
                elapsed = time.time() - step_start
                if record.image_description:
                    preview = record.image_description[:250] + ("..." if len(record.image_description) > 250 else "")
                    logger.info("[%s] Scene description (%.2fs): %s", job.image_path.name, elapsed, preview)
        except Exception as exc:
            elapsed = time.time() - step_start
            msg = f"VLM scene description error: {exc}"
            logger.error("[%s] %s (%.2fs)", job.image_path.name, msg, elapsed)
            record.image_description = f"ERROR: {msg}"

        # --- 1. VLM Text Extraction ---
        step_start = time.time()
        TEXT_EXTRACTION_PROMPT = """Extract ALL visible text:
- Captions, overlays, screen text
- Signs, posters, objects
If none, return: NONE"""
        try:
            extracted_text = self._smolvlm.describe_images(
                [str(preprocessed_path)], TEXT_EXTRACTION_PROMPT.strip()
            )
            # Check if VLM returned None (API failure)
            if extracted_text is None:
                msg = "VLM API returned None (possible insufficient credits or API error)"
                logger.error("[%s] %s", job.image_path.name, msg)
                record.error_ocr = msg
            else:
                cleaned_text = _normalize_vlm_output(extracted_text)
                from domain.entities import OcrResult
                if cleaned_text and not _is_none_output(cleaned_text):
                    ocr_result = OcrResult(
                        ocr_text_raw=cleaned_text,
                        ocr_text_clean=cleaned_text,
                        ocr_char_count=len(cleaned_text),
                        ocr_word_count=len(cleaned_text.split()),
                        ocr_detected_bool=True,
                    )
                    record.ocr_result = ocr_result
                else:
                    record.ocr_result = OcrResult(
                        ocr_text_raw="NONE",
                        ocr_text_clean="NONE",
                        ocr_char_count=0,
                        ocr_word_count=0,
                        ocr_detected_bool=False,
                    )
                elapsed = time.time() - step_start
                logger.info("[%s] Text extraction completed (%.2fs)", job.image_path.name, elapsed)
        except Exception as exc:
            elapsed = time.time() - step_start
            msg = f"VLM text extraction error: {exc}"
            logger.error("[%s] %s (%.2fs)", job.image_path.name, msg, elapsed)
            record.error_ocr = msg

        # --- 2. Sentiment Analysis (only if text exists) ---
        step_start = time.time()
        try:
            if record.ocr_result and record.ocr_result.ocr_detected_bool and not _is_none_output(record.ocr_result.ocr_text_clean):
                record.sentiment_result = self._sentiment.analyze(record.ocr_result.ocr_text_clean)
                elapsed = time.time() - step_start
                logger.info("[%s] Sentiment analysis completed (%.2fs)", job.image_path.name, elapsed)
        except Exception as exc:
            elapsed = time.time() - step_start
            msg = f"Sentiment analysis error: {exc}"
            logger.error("[%s] %s (%.2fs)", job.image_path.name, msg, elapsed)
            record.error_ocr = (record.error_ocr or "") + f" | {msg}"

        # --- 3. VLM Emotional Visual Reasoning ---
        step_start = time.time()
        EMOTION_REASONING_PROMPT = """Analyze emotional tone from visual cues:
- Face: expressions, head position (bowed/upright)
- Body: posture (slumped/upright), hands (covering face, clenched)
- Colors: dark/muted vs bright/vibrant
- Lighting: shadows, dim vs well-lit
- Setting: isolated vs social, empty vs full
Format:
Emotion: [sad/happy/anxious/neutral]
Evidence: [specific visual details]
No person? 'Emotion: UNKNOWN'"""
        try:
            vlm_emotion_desc = self._smolvlm.describe_images(
                [str(preprocessed_path)], EMOTION_REASONING_PROMPT.strip()
            )
            # Check if VLM returned None (API failure)
            if vlm_emotion_desc is None:
                msg = "VLM API returned None (possible insufficient credits or API error)"
                logger.error("[%s] %s", job.image_path.name, msg)
                record.vlm_emotion_description = f"ERROR: {msg}"
            else:
                record.vlm_emotion_description = _normalize_vlm_output(vlm_emotion_desc)
                elapsed = time.time() - step_start
                logger.info("[%s] Emotion reasoning completed (%.2fs)", job.image_path.name, elapsed)
        except Exception as exc:
            elapsed = time.time() - step_start
            msg = f"VLM emotional reasoning error: {exc}"
            logger.error("[%s] %s (%.2fs)", job.image_path.name, msg, elapsed)
            record.vlm_emotion_description = f"ERROR: {msg}"
            record.vlm_emotion_description = f"ERROR: {msg}"

        # --- 4. Face Classifier ---
        step_start = time.time()
        try:
            emotion_image = self._preprocessor.load_for_emotion(job.image_path)
            record.emotion_result = self._emotion.detect(emotion_image)
            elapsed = time.time() - step_start
            logger.info("[%s] Face emotion detection completed (%.2fs)", job.image_path.name, elapsed)
        except Exception as exc:
            elapsed = time.time() - step_start
            msg = f"Emotion classifier error: {exc}"
            logger.error("[%s] %s (%.2fs)", job.image_path.name, msg, elapsed)
            record.error_emotion = msg

        # --- 5. Fusion Layer: VLM + Classifier (TEMPORARILY SKIPPED FOR SPEED) ---
        # Skipping fusion to reduce processing time from ~12s to ~6s
        record.fused_emotion_assessment = "SKIPPED - Using direct classifier results for speed"
        logger.info("[%s] Fusion layer skipped (speed optimization)", job.image_path.name)
        
        # --- Log total pipeline time ---
        total_elapsed = time.time() - pipeline_start
        logger.info("[%s] ⚡ PIPELINE COMPLETE - Total time: %.2f seconds", job.image_path.name, total_elapsed)

        return record


# ---------------------------------------------------------------------------
# Use case: RunBatchProcessing
# ---------------------------------------------------------------------------


class RunBatchProcessing:
    """Discover images, build jobs, process, and persist results."""

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

        # ---- Persist with complete VLM data (CSV + MongoDB) ----------------
        vlm_output = self._storage.save_vlm_complete(records, overwrite=overwrite)
        summary.ocr_sentiment_output = str(vlm_output)
        summary.face_emotion_output = str(vlm_output)

        summary.finished_at = datetime.utcnow()
        summary.log_summary()
        return summary
