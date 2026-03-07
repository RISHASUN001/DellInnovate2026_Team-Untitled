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
        record = ImageRecord(job=job, processed_at=datetime.utcnow())

        # --- 0. VLM Scene Description ---
        IMAGE_DESCRIPTION_PROMPT = (
            """
            Describe what is happening in this image in 2-3 sentences.
            Include:
            - Who or what is visible (people, objects, animals, etc.)
            - What they are doing (actions, postures, movements)
            - The setting or context
            - Any notable details about body language or positioning
            
            Be specific and concrete (e.g., 'man sitting with his head resting on his hand' not 'person present').
            """
        )
        try:
            scene_desc = self._smolvlm.describe_images(
                [str(job.image_path)], IMAGE_DESCRIPTION_PROMPT.strip()
            )
            record.image_description = _normalize_vlm_output(scene_desc)
            if record.image_description:
                preview = record.image_description[:100] + ("..." if len(record.image_description) > 100 else "")
                logger.info("[%s] Scene description: %s", job.image_path.name, preview)
        except Exception as exc:
            msg = f"VLM scene description error: {exc}"
            logger.error("[%s] %s", job.image_path.name, msg)
            record.image_description = f"ERROR: {msg}"

        # --- 1. VLM Text Extraction ---
        TEXT_EXTRACTION_PROMPT = (
            """
            Extract all visible text from this image exactly as written.
            Do not summarize.
            Do not interpret.
            Return only the raw text.
            If no text is visible, return: NONE.
            """
        )
        try:
            extracted_text = self._smolvlm.describe_images(
                [str(job.image_path)], TEXT_EXTRACTION_PROMPT.strip()
            )
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
        except Exception as exc:
            msg = f"VLM text extraction error: {exc}"
            logger.error("[%s] %s", job.image_path.name, msg)
            record.error_ocr = msg

        # --- 2. Sentiment Analysis (only if text exists) ---
        try:
            if record.ocr_result and record.ocr_result.ocr_detected_bool and not _is_none_output(record.ocr_result.ocr_text_clean):
                record.sentiment_result = self._sentiment.analyze(record.ocr_result.ocr_text_clean)
        except Exception as exc:
            msg = f"Sentiment analysis error: {exc}"
            logger.error("[%s] %s", job.image_path.name, msg)
            record.error_ocr = (record.error_ocr or "") + f" | {msg}"

        # --- 3. VLM Emotional Visual Reasoning ---
        EMOTION_REASONING_PROMPT = (
            """
            Based on the visible cues in this image, infer the person's emotional or mental state.
            Consider: facial expression, head/hand posture, body language, positioning, and overall demeanor.
            
            If you see postures like:
            - Head in hand: thoughtful, contemplative, stressed, or bored
            - Slouching: sad, tired, or defeated
            - Upright/engaged: alert, attentive, or interested
            - Hands on face: worried, frustrated, or concentrating
            
            Output format:
            Emotion: <single best emotion label>
            Evidence: <1-2 specific observations from the image that support this emotion>

            If no person is clearly visible, output exactly:
            Emotion: UNKNOWN
            Evidence: Person not clearly visible.
            """
        )
        try:
            vlm_emotion_desc = self._smolvlm.describe_images(
                [str(job.image_path)], EMOTION_REASONING_PROMPT.strip()
            )
            record.vlm_emotion_description = _normalize_vlm_output(vlm_emotion_desc)
        except Exception as exc:
            msg = f"VLM emotional reasoning error: {exc}"
            logger.error("[%s] %s", job.image_path.name, msg)
            record.vlm_emotion_description = f"ERROR: {msg}"

        # --- 4. Face Classifier ---
        try:
            emotion_image = self._preprocessor.load_for_emotion(job.image_path)
            record.emotion_result = self._emotion.detect(emotion_image)
        except Exception as exc:
            msg = f"Emotion classifier error: {exc}"
            logger.error("[%s] %s", job.image_path.name, msg)
            record.error_emotion = msg

        # --- 5. Fusion Layer: VLM + Classifier ---
        try:
            emotion_label = record.emotion_result.emotion_label if record.emotion_result else "NONE"
            emotion_conf = record.emotion_result.emotion_score if record.emotion_result else 0.0
            fusion_prompt = f"""
            An emotion classifier predicted: {emotion_label} (confidence: {emotion_conf:.2f})
            
            Scene description from image analysis: {record.image_description}
            
            Do you agree with this prediction based on the visible posture, facial expression, and body language?
            
            Output format:
            Agreement: <AGREE or DISAGREE>
            RefinedEmotion: <emotion label>
            Rationale: <1-2 sentences explaining why you agree or disagree, with specific visual evidence>
            """
            fused_assessment = self._smolvlm.describe_images(
                [str(job.image_path)], fusion_prompt.strip()
            )
            record.fused_emotion_assessment = _normalize_vlm_output(fused_assessment)
        except Exception as exc:
            msg = f"Fusion VLM error: {exc}"
            logger.error("[%s] %s", job.image_path.name, msg)
            record.fused_emotion_assessment = f"ERROR: {msg}"

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
