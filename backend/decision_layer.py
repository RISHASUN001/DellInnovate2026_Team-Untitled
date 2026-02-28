"""
backend/decision_layer.py

This module loads the saved LR calibration artifacts (joblib + meta json)
and applies them to Stage2 user-level outputs as the "decision layer".

Outputs added to Stage2 df:
- calibrated_prob_attention (0..1)
- calibrated_requires_attention (bool) using recommended threshold
- calibrated_risk_score (0..100)
- calibrated_priority (low/medium/high/critical) using triage thresholds
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import json
import joblib
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CalibrationArtifacts:
    model: Any
    features_used: List[str]
    threshold: float
    triage_thresholds: Dict[str, float]


def load_calibration_artifacts(
    model_path: str | Path = "evaluation/artifacts/calibration_lr.joblib",
    meta_path: str | Path = "evaluation/artifacts/calibration_meta.json",
) -> CalibrationArtifacts:
    model_path = Path(model_path)
    meta_path = Path(meta_path)

    if not model_path.exists():
        raise FileNotFoundError(f"Calibration model not found: {model_path}")
    if not meta_path.exists():
        raise FileNotFoundError(f"Calibration metadata not found: {meta_path}")

    model = joblib.load(model_path)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    features_used = list(meta.get("features_used", []))

    # recommended decision threshold (selected on test set)
    threshold = float(meta.get("best_threshold_on_test", {}).get("thr", 0.5))

    triage = meta.get("triage_thresholds_from_full_data", {}) or {}
    triage_thresholds = {
        "low_to_med_prob": float(triage.get("low_to_med_prob", 0.5)),
        "med_to_high_prob": float(triage.get("med_to_high_prob", 0.75)),
        "high_to_critical_prob": float(triage.get("high_to_critical_prob", 0.9)),
    }

    return CalibrationArtifacts(
        model=model,
        features_used=features_used,
        threshold=threshold,
        triage_thresholds=triage_thresholds,
    )


def apply_calibrated_decision_layer(
    df_stage2: pd.DataFrame,
    artifacts: CalibrationArtifacts,
    *,
    inplace: bool = False,
) -> pd.DataFrame:
    """
    Apply LR calibration model to Stage2 dataframe.
    Missing feature columns are created and filled with 0.0.
    """
    df = df_stage2 if inplace else df_stage2.copy()

    # Ensure feature columns exist
    for col in artifacts.features_used:
        if col not in df.columns:
            df[col] = 0.0

    X = df[artifacts.features_used].fillna(0.0).astype(float).to_numpy()
    prob = artifacts.model.predict_proba(X)[:, 1]

    df["calibrated_prob_attention"] = prob
    df["calibrated_requires_attention"] = prob >= artifacts.threshold
    df["calibrated_risk_score"] = np.clip(prob * 100.0, 0.0, 100.0)

    t = artifacts.triage_thresholds

    def _priority(p: float) -> str:
        if p >= t["high_to_critical_prob"]:
            return "critical"
        if p >= t["med_to_high_prob"]:
            return "high"
        if p >= t["low_to_med_prob"]:
            return "medium"
        return "low"

    df["calibrated_priority"] = [_priority(float(p)) for p in prob]
    return df


def apply_calibration_to_csv(
    stage2_csv_path: str | Path,
    out_csv_path: Optional[str | Path] = None,
    *,
    model_path: str | Path = "evaluation/artifacts/calibration_lr.joblib",
    meta_path: str | Path = "evaluation/artifacts/calibration_meta.json",
) -> Path:
    """
    Convenience wrapper:
    - reads Stage2 CSV
    - applies calibration
    - writes a calibrated CSV
    """
    stage2_csv_path = Path(stage2_csv_path)
    if out_csv_path is None:
        out_csv_path = stage2_csv_path.with_name(stage2_csv_path.stem + "_calibrated.csv")
    out_csv_path = Path(out_csv_path)

    df = pd.read_csv(stage2_csv_path)
    artifacts = load_calibration_artifacts(model_path=model_path, meta_path=meta_path)
    df2 = apply_calibrated_decision_layer(df, artifacts)
    df2.to_csv(out_csv_path, index=False)
    return out_csv_path