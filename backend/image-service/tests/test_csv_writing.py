"""
Tests for CSV writing via CsvStorageAdapter.

These tests use the real adapter with a tmp_path directory and stub domain
objects — no ML models required.
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pytest

from adapters.storage_adapter import (
    CsvStorageAdapter,
    FACE_EMOTION_COLUMNS,
    OCR_SENTIMENT_COLUMNS,
)
from application.filename_parser import parse_image_filename
from domain.entities import (
    EmotionResult,
    ImageJob,
    ImageMetadata,
    ImageRecord,
    OcrResult,
    SentimentResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(
    handle: str = "test_user",
    post_date: date = date(2024, 1, 1),
    index: int = 0,
    with_ocr: bool = True,
    with_sentiment: bool = True,
    with_emotion: bool = True,
    path: Optional[Path] = None,
) -> ImageRecord:
    meta = ImageMetadata(ig_handle=handle, post_date=post_date, image_index=index)
    job = ImageJob(
        image_path=path or Path(f"{handle}__{post_date.strftime('%Y%m%d')}__{index}.jpg"),
        metadata=meta,
    )
    rec = ImageRecord(job=job, processed_at=datetime(2024, 6, 1, 12, 0, 0))

    if with_ocr:
        rec.ocr_result = OcrResult(
            ocr_text_raw="Hello world raw",
            ocr_text_clean="Hello world clean",
            ocr_char_count=17,
            ocr_word_count=3,
            ocr_detected_bool=True,
        )
    if with_sentiment:
        rec.sentiment_result = SentimentResult(
            sentiment_label="POSITIVE",
            sentiment_score=0.95,
        )
    if with_emotion:
        rec.emotion_result = EmotionResult(
            face_detected_bool=True,
            emotion_label="happy",
            emotion_score=0.88,
            model_name="dima806/facial_emotions_image_detection",
        )

    return rec


# ---------------------------------------------------------------------------
# Column / header tests
# ---------------------------------------------------------------------------


def test_ocr_sentiment_csv_columns(tmp_path: Path) -> None:
    adapter = CsvStorageAdapter(output_folder=tmp_path)
    adapter.save_ocr_sentiment([_make_record()], overwrite=True)

    out = tmp_path / "ocr_sentiment_results.csv"
    with out.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == OCR_SENTIMENT_COLUMNS


def test_face_emotion_csv_columns(tmp_path: Path) -> None:
    adapter = CsvStorageAdapter(output_folder=tmp_path)
    adapter.save_emotion([_make_record()], overwrite=True)

    out = tmp_path / "face_emotion_results.csv"
    with out.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == FACE_EMOTION_COLUMNS


# ---------------------------------------------------------------------------
# Row content tests
# ---------------------------------------------------------------------------


def test_ocr_sentiment_row_values(tmp_path: Path) -> None:
    rec = _make_record(handle="brand_x", post_date=date(2023, 12, 31), index=7)
    adapter = CsvStorageAdapter(output_folder=tmp_path)
    adapter.save_ocr_sentiment([rec], overwrite=True)

    out = tmp_path / "ocr_sentiment_results.csv"
    rows = list(csv.DictReader(out.open(newline="", encoding="utf-8")))
    assert len(rows) == 1
    row = rows[0]

    assert row["ig_handle"] == "brand_x"
    assert row["post_date"] == "2023-12-31"
    assert row["image_index"] == "7"
    assert row["ocr_text_raw"] == "Hello world raw"
    assert row["ocr_text_clean"] == "Hello world clean"
    assert row["sentiment_label"] == "POSITIVE"
    assert float(row["sentiment_score"]) == pytest.approx(0.95)
    assert row["ocr_char_count"] == "17"
    assert row["ocr_word_count"] == "3"
    assert row["ocr_detected_bool"] == "True"


def test_face_emotion_row_values(tmp_path: Path) -> None:
    rec = _make_record(handle="influencer", post_date=date(2024, 3, 15), index=2)
    adapter = CsvStorageAdapter(output_folder=tmp_path)
    adapter.save_emotion([rec], overwrite=True)

    out = tmp_path / "face_emotion_results.csv"
    rows = list(csv.DictReader(out.open(newline="", encoding="utf-8")))
    assert len(rows) == 1
    row = rows[0]

    assert row["face_detected_bool"] == "True"
    assert row["emotion_label"] == "happy"
    assert float(row["emotion_score"]) == pytest.approx(0.88)
    assert row["model_name"] == "dima806/facial_emotions_image_detection"


# ---------------------------------------------------------------------------
# Missing optional results → empty / zero placeholders
# ---------------------------------------------------------------------------


def test_ocr_sentiment_missing_results(tmp_path: Path) -> None:
    rec = _make_record(with_ocr=False, with_sentiment=False, with_emotion=True)
    adapter = CsvStorageAdapter(output_folder=tmp_path)
    adapter.save_ocr_sentiment([rec], overwrite=True)

    out = tmp_path / "ocr_sentiment_results.csv"
    rows = list(csv.DictReader(out.open(newline="", encoding="utf-8")))
    row = rows[0]

    assert row["ocr_text_raw"] == ""
    assert row["sentiment_label"] == ""
    assert row["ocr_char_count"] == "0"
    assert row["ocr_detected_bool"] == "False"


# ---------------------------------------------------------------------------
# Overwrite vs append behaviour
# ---------------------------------------------------------------------------


def test_overwrite_replaces_existing_file(tmp_path: Path) -> None:
    adapter = CsvStorageAdapter(output_folder=tmp_path)
    adapter.save_ocr_sentiment([_make_record(handle="first")], overwrite=True)
    adapter.save_ocr_sentiment([_make_record(handle="second")], overwrite=True)

    out = tmp_path / "ocr_sentiment_results.csv"
    rows = list(csv.DictReader(out.open(newline="", encoding="utf-8")))
    assert len(rows) == 1
    assert rows[0]["ig_handle"] == "second"


def test_append_adds_to_existing_file(tmp_path: Path) -> None:
    adapter = CsvStorageAdapter(output_folder=tmp_path)
    adapter.save_ocr_sentiment([_make_record(handle="first")], overwrite=True)
    adapter.save_ocr_sentiment([_make_record(handle="second")], overwrite=False)

    out = tmp_path / "ocr_sentiment_results.csv"
    rows = list(csv.DictReader(out.open(newline="", encoding="utf-8")))
    assert len(rows) == 2
    handles = {r["ig_handle"] for r in rows}
    assert handles == {"first", "second"}


# ---------------------------------------------------------------------------
# Multiple records
# ---------------------------------------------------------------------------


def test_multiple_records_written_in_order(tmp_path: Path) -> None:
    records = [_make_record(handle=f"user{i}", index=i) for i in range(5)]
    adapter = CsvStorageAdapter(output_folder=tmp_path)
    adapter.save_ocr_sentiment(records, overwrite=True)

    out = tmp_path / "ocr_sentiment_results.csv"
    rows = list(csv.DictReader(out.open(newline="", encoding="utf-8")))
    assert len(rows) == 5
    for i, row in enumerate(rows):
        assert row["image_index"] == str(i)


# ---------------------------------------------------------------------------
# Output folder created automatically
# ---------------------------------------------------------------------------


def test_output_folder_created_automatically(tmp_path: Path) -> None:
    deep_folder = tmp_path / "a" / "b" / "c"
    adapter = CsvStorageAdapter(output_folder=deep_folder)
    adapter.save_ocr_sentiment([_make_record()], overwrite=True)
    assert (deep_folder / "ocr_sentiment_results.csv").exists()
