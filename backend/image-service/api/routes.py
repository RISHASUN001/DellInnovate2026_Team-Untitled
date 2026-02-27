"""
FastAPI route definitions for the image-service.

Endpoints
---------
POST /run
    Trigger a batch processing run.  Accepts optional JSON body parameters
    to override input_folder, set overwrite flag, and cap the number of images.

GET /health
    Lightweight liveness / readiness probe.

GET /outputs
    List files in the output folder.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from application.use_cases import BatchRunSummary, RunBatchProcessing
from config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class RunRequest(BaseModel):
    """Optional overrides for the batch run."""

    input_folder: Optional[str] = None
    overwrite: bool = False
    max_images: int = 0  # 0 = no cap


class RunResponse(BaseModel):
    status: str
    total_images: int
    ocr_detections: int
    sentiment_inferences: int
    face_detections: int
    ocr_failures: int
    emotion_failures: int
    ocr_sentiment_output: Optional[str]
    face_emotion_output: Optional[str]
    elapsed_seconds: Optional[float]


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class OutputsResponse(BaseModel):
    output_folder: str
    files: list[str]


# ---------------------------------------------------------------------------
# Dependency — injected runner (populated at startup in main.py)
# ---------------------------------------------------------------------------

_runner: Optional[RunBatchProcessing] = None


def set_runner(runner: RunBatchProcessing) -> None:
    global _runner
    _runner = runner


def get_runner() -> RunBatchProcessing:
    if _runner is None:
        raise RuntimeError("Runner not initialised. Call set_runner() at startup.")
    return _runner


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/run", response_model=RunResponse, summary="Run batch processing")
async def run_batch(body: RunRequest = RunRequest()) -> RunResponse:
    """Trigger the full batch processing pipeline.

    - Scans ``input_folder`` (or the configured default) recursively.
    - Parses filenames to build ``ImageJob``s.
    - Runs OCR → sentiment and face → emotion pipelines in sequence.
    - Persists results to the outputs folder.
    """
    runner = get_runner()

    input_path: Optional[Path] = (
        Path(body.input_folder) if body.input_folder else None
    )

    if input_path and not input_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"input_folder '{input_path}' does not exist.",
        )

    try:
        summary: BatchRunSummary = runner.execute(
            input_folder=input_path,
            overwrite=body.overwrite,
            max_images=body.max_images,
        )
    except Exception as exc:
        logger.exception("Batch run failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    elapsed: Optional[float] = None
    if summary.finished_at and summary.started_at:
        elapsed = (summary.finished_at - summary.started_at).total_seconds()

    return RunResponse(
        status="ok",
        total_images=summary.total_images,
        ocr_detections=summary.ocr_detections,
        sentiment_inferences=summary.sentiment_inferences,
        face_detections=summary.face_detections,
        ocr_failures=summary.ocr_failures,
        emotion_failures=summary.emotion_failures,
        ocr_sentiment_output=(
            str(summary.ocr_sentiment_output) if summary.ocr_sentiment_output else None
        ),
        face_emotion_output=(
            str(summary.face_emotion_output) if summary.face_emotion_output else None
        ),
        elapsed_seconds=elapsed,
    )


@router.get("/health", response_model=HealthResponse, summary="Health check")
async def health() -> HealthResponse:
    """Returns service liveness.  Used by Docker HEALTHCHECK."""
    return HealthResponse(
        status="healthy",
        service="image-service",
        version="1.0.0",
    )


@router.get("/outputs", response_model=OutputsResponse, summary="List output files")
async def list_outputs() -> OutputsResponse:
    """Return all files currently in the outputs folder."""
    out_folder = settings.output_folder
    if not out_folder.exists():
        return OutputsResponse(output_folder=str(out_folder), files=[])

    files = sorted(
        str(p.relative_to(out_folder))
        for p in out_folder.rglob("*")
        if p.is_file()
    )
    return OutputsResponse(output_folder=str(out_folder), files=files)
