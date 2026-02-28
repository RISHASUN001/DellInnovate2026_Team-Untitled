"""
Tests for error handling in the processing pipeline.

All tests use stub/fake adapters — no real ML models are loaded.
The goal is to verify that per-image errors are captured in the record
and never propagate to crash the batch run.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from application.use_cases import ProcessSingleImage, RunBatchProcessing
from domain.entities import (
    EmotionResult,
    ImageJob,
    ImageMetadata,
    ImageRecord,
    OcrResult,
    SentimentResult,
)
from ports.emotion_port import EmotionPort
from adapters.smolvlm_adapter import SmolVLMAdapter
from ports.preprocessing_port import PreprocessingPort
from ports.sentiment_port import SentimentPort
from ports.storage_port import StoragePort


# ---------------------------------------------------------------------------
# Stub port implementations
# ---------------------------------------------------------------------------


class _DummyPreprocessor(PreprocessingPort):
    def load_for_ocr(self, path: Path) -> Image.Image:
        return Image.new("RGB", (10, 10))

    def load_for_emotion(self, path: Path) -> Image.Image:
        return Image.new("RGB", (10, 10))


class _ExplodingPreprocessorOcr(PreprocessingPort):
    """Raises on load_for_ocr but succeeds for emotion."""

    def load_for_ocr(self, path: Path) -> Image.Image:
        raise RuntimeError("Simulated OCR preprocessing failure")

    def load_for_emotion(self, path: Path) -> Image.Image:
        return Image.new("RGB", (10, 10))


class _ExplodingPreprocessorEmotion(PreprocessingPort):
    """Succeeds for OCR but raises on load_for_emotion."""

    def load_for_ocr(self, path: Path) -> Image.Image:
        return Image.new("RGB", (10, 10))

    def load_for_emotion(self, path: Path) -> Image.Image:
        raise RuntimeError("Simulated emotion preprocessing failure")



class _GoodSmolVLM(SmolVLMAdapter):
    def describe_images(self, image_paths, prompt_text):
        return "hello"



class _ExplodingSmolVLM(SmolVLMAdapter):
    def describe_images(self, image_paths, prompt_text):
        raise RuntimeError("Simulated OCR failure")


class _GoodSentiment(SentimentPort):
    def analyze(self, text: str) -> SentimentResult:
        return SentimentResult(sentiment_label="POSITIVE", sentiment_score=0.9)


class _ExplodingSentiment(SentimentPort):
    def analyze(self, text: str) -> SentimentResult:
        raise RuntimeError("Simulated sentiment failure")


class _GoodEmotion(EmotionPort):
    def detect(self, image: Image.Image) -> EmotionResult:
        return EmotionResult(
            face_detected_bool=True, emotion_label="happy",
            emotion_score=0.8, model_name="test-model"
        )


class _ExplodingEmotion(EmotionPort):
    def detect(self, image: Image.Image) -> EmotionResult:
        raise RuntimeError("Simulated emotion failure")


class _DummyStorage(StoragePort):
    def __init__(self) -> None:
        self.ocr_calls: List[List[ImageRecord]] = []
        self.emotion_calls: List[List[ImageRecord]] = []

    def save_ocr_sentiment(self, records, overwrite=False) -> Path:
        self.ocr_calls.append(records)
        return Path("outputs/ocr_sentiment_results.csv")

    def save_emotion(self, records, overwrite=False) -> Path:
        self.emotion_calls.append(records)
        return Path("outputs/face_emotion_results.csv")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_job(name: str = "user__20240101__0.jpg") -> ImageJob:
    meta = ImageMetadata(
        ig_handle="user", post_date=date(2024, 1, 1), image_index=0
    )
    return ImageJob(image_path=Path(name), metadata=meta)


# ---------------------------------------------------------------------------
# ProcessSingleImage error-capture tests
# ---------------------------------------------------------------------------



def test_ocr_failure_captured_emotion_still_runs() -> None:
    """A vision-language exception must be captured; emotion pipeline must still execute."""
    use_case = ProcessSingleImage(
        preprocessor=_DummyPreprocessor(),
        smolvlm=_ExplodingSmolVLM(),
        sentiment=_GoodSentiment(),
        emotion=_GoodEmotion(),
    )
    record = use_case.execute(_make_job())

    assert record.error_ocr is not None
    assert "Simulated OCR failure" in record.error_ocr

    # Emotion pipeline ran even though vision-language failed
    assert record.emotion_result is not None
    assert record.emotion_result.face_detected_bool is True
    assert record.error_emotion is None



def test_emotion_failure_captured_ocr_still_runs() -> None:
    """An emotion exception must be captured; vision-language pipeline must succeed."""
    use_case = ProcessSingleImage(
        preprocessor=_DummyPreprocessor(),
        smolvlm=_GoodSmolVLM(),
        sentiment=_GoodSentiment(),
        emotion=_ExplodingEmotion(),
    )
    record = use_case.execute(_make_job())

    assert record.error_emotion is not None
    assert "Simulated emotion failure" in record.error_emotion

    # Vision-language succeeded
    assert record.ocr_result is not None
    assert record.ocr_result.ocr_detected_bool is True
    assert record.error_ocr is None



def test_both_pipelines_fail_record_has_both_errors() -> None:
    use_case = ProcessSingleImage(
        preprocessor=_DummyPreprocessor(),
        smolvlm=_ExplodingSmolVLM(),
        sentiment=_GoodSentiment(),
        emotion=_ExplodingEmotion(),
    )
    record = use_case.execute(_make_job())

    assert record.error_ocr is not None
    assert record.error_emotion is not None
    assert record.ocr_result is None
    assert record.emotion_result is None



def test_sentiment_failure_captured_ocr_result_preserved() -> None:
    use_case = ProcessSingleImage(
        preprocessor=_DummyPreprocessor(),
        smolvlm=_GoodSmolVLM(),
        sentiment=_ExplodingSentiment(),
        emotion=_GoodEmotion(),
    )
    record = use_case.execute(_make_job())

    # Vision-language ran, sentiment failed — error captured in ocr pipeline slot
    assert record.error_ocr is not None
    assert "Simulated sentiment failure" in record.error_ocr
    # Vision-language result was set before sentiment failed
    assert record.ocr_result is not None


def test_preprocessing_ocr_failure_captured() -> None:
    use_case = ProcessSingleImage(
        preprocessor=_ExplodingPreprocessorOcr(),
        ocr=_GoodOcr(),
        sentiment=_GoodSentiment(),
        emotion=_GoodEmotion(),
    )
    record = use_case.execute(_make_job())
    assert record.error_ocr is not None
    # Emotion should still succeed
    assert record.emotion_result is not None
    assert record.error_emotion is None


def test_preprocessing_emotion_failure_captured() -> None:
    use_case = ProcessSingleImage(
        preprocessor=_ExplodingPreprocessorEmotion(),
        ocr=_GoodOcr(),
        sentiment=_GoodSentiment(),
        emotion=_GoodEmotion(),
    )
    record = use_case.execute(_make_job())
    assert record.error_emotion is not None
    # OCR should succeed
    assert record.ocr_result is not None
    assert record.error_ocr is None


# ---------------------------------------------------------------------------
# RunBatchProcessing — batch continues despite per-image errors
# ---------------------------------------------------------------------------


def test_batch_continues_on_per_image_errors(tmp_path: Path) -> None:
    """Batch must process all images even if every single one raises."""
    # Create valid-named image files on disk (needed for discover_images)
    for i in range(3):
        (tmp_path / f"user__20240101__{i}.jpg").touch()

    use_case = ProcessSingleImage(
        preprocessor=_ExplodingPreprocessorOcr(),
        ocr=_ExplodingOcr(),
        sentiment=_GoodSentiment(),
        emotion=_GoodEmotion(),
    )
    storage = _DummyStorage()
    runner = RunBatchProcessing(process_single=use_case, storage=storage)

    summary = runner.execute(input_folder=tmp_path, overwrite=True)

    assert summary.total_images == 3
    assert summary.ocr_failures == 3
    # Emotion should still have run despite OCR failures
    assert summary.emotion_failures == 0
    # Storage was called once with all records
    assert len(storage.ocr_calls) == 1
    assert len(storage.ocr_calls[0]) == 3


def test_batch_counts_correct_stats(tmp_path: Path) -> None:
    for i in range(4):
        (tmp_path / f"creator__20240601__{i}.jpg").touch()

    use_case = ProcessSingleImage(
        preprocessor=_DummyPreprocessor(),
        ocr=_GoodOcr(),
        sentiment=_GoodSentiment(),
        emotion=_GoodEmotion(),
    )
    storage = _DummyStorage()
    runner = RunBatchProcessing(process_single=use_case, storage=storage)

    summary = runner.execute(input_folder=tmp_path, overwrite=True)

    assert summary.total_images == 4
    assert summary.ocr_detections == 4
    assert summary.sentiment_inferences == 4
    assert summary.face_detections == 4
    assert summary.ocr_failures == 0
    assert summary.emotion_failures == 0


def test_batch_skips_non_conforming_filenames(tmp_path: Path) -> None:
    (tmp_path / "user__20240101__0.jpg").touch()
    (tmp_path / "bad_filename.jpg").touch()
    (tmp_path / "also_bad.png").touch()

    use_case = ProcessSingleImage(
        preprocessor=_DummyPreprocessor(),
        ocr=_GoodOcr(),
        sentiment=_GoodSentiment(),
        emotion=_GoodEmotion(),
    )
    storage = _DummyStorage()
    runner = RunBatchProcessing(process_single=use_case, storage=storage)

    summary = runner.execute(input_folder=tmp_path, overwrite=True)

    # Only the correctly-named file should be processed
    assert summary.total_images == 1


def test_batch_respects_max_images_cap(tmp_path: Path) -> None:
    for i in range(10):
        (tmp_path / f"user__20240101__{i}.jpg").touch()

    use_case = ProcessSingleImage(
        preprocessor=_DummyPreprocessor(),
        ocr=_GoodOcr(),
        sentiment=_GoodSentiment(),
        emotion=_GoodEmotion(),
    )
    storage = _DummyStorage()
    runner = RunBatchProcessing(process_single=use_case, storage=storage)

    summary = runner.execute(input_folder=tmp_path, max_images=3)

    assert summary.total_images == 3
