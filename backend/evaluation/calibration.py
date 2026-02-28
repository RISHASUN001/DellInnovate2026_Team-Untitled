# backend/evaluation/calibration.py
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any

import json
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

from evaluation.scorecard_eval import _ensure_bool


ROOT = Path(__file__).resolve().parents[1]
STAGE2 = ROOT / "stage2_user_analysis.csv"
OUT_CSV = ROOT / "calibrated_user_probs.csv"

# NEW: artifacts directory for deployment/inference
ARTIFACT_DIR = ROOT / "evaluation" / "artifacts"
MODEL_PATH = ARTIFACT_DIR / "calibration_lr.joblib"
META_PATH = ARTIFACT_DIR / "calibration_meta.json"


FEATURES_DEFAULT = [
    "Risk_Score",
    "Distortion_Rate",
    "Volatility_Score",
    "Rapid_Shifts",
    "Comment_Bursts",
    "Long_Gaps",
]


def _prf(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    p, r, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
    return {"precision": float(p), "recall": float(r), "f1": float(f1)}


def fit_calibration(
    stage2_path: Path = STAGE2,
    label_col: str = "Requires_Attention",
    features: list[str] = FEATURES_DEFAULT,
    test_size: float = 0.30,
    random_state: int = 42,
) -> Dict[str, Any]:
    """
    Train a logistic regression decision layer on Stage2 user features to produce:
      - calibrated_prob_attention (0..1)
      - a recommended classification threshold
      - suggested triage thresholds based on quantiles

    NEW: persists model + meta so Stage2/board can load it later.
    """
    df = pd.read_csv(stage2_path)
    df[label_col] = df[label_col].apply(_ensure_bool)

    # Ensure features exist
    usable_features = [f for f in features if f in df.columns]
    if not usable_features:
        raise ValueError(f"No requested features found. Requested={features}, have={list(df.columns)}")

    X = df[usable_features].fillna(0.0).astype(float).to_numpy()
    y = df[label_col].astype(bool).to_numpy()

    # If only one class exists, calibration is meaningless
    if len(np.unique(y)) < 2:
        raise ValueError("Label has only one class in data; need both True/False to calibrate.")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=2000, class_weight="balanced")),
        ]
    )

    model.fit(X_train, y_train)

    prob_test = model.predict_proba(X_test)[:, 1]
    auc = float(roc_auc_score(y_test, prob_test))

    # Choose a decision threshold (maximize F1 on the held-out test split)
    thresholds = np.linspace(0.1, 0.9, 81)
    best = {"thr": 0.5, "f1": -1.0, "precision": 0.0, "recall": 0.0}
    for thr in thresholds:
        pred = prob_test >= thr
        prf = _prf(y_test, pred)
        if prf["f1"] > best["f1"]:
            best = {"thr": float(thr), **prf}

    # Fit on full data and output calibrated probs for all users
    prob_all = model.predict_proba(X)[:, 1]
    out_df = df.copy()
    out_df["calibrated_prob_attention"] = prob_all
    out_df.to_csv(OUT_CSV, index=False)

    # Suggested triage thresholds from probability quantiles
    q50, q75, q90 = np.quantile(prob_all, [0.5, 0.75, 0.90])
    triage = {
        "low_to_med_prob": float(q50),
        "med_to_high_prob": float(q75),
        "high_to_critical_prob": float(q90),
    }

    # NEW: persist artifacts for inference
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    meta = {
        "features_used": usable_features,
        "label_col": label_col,
        "test_auroc": auc,
        "best_threshold_on_test": best,
        "triage_thresholds_from_full_data": triage,
        "trained_at_utc": pd.Timestamp.utcnow().isoformat(),
    }
    META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return {
        "features_used": usable_features,
        "test_auroc": auc,
        "best_threshold_on_test": best,
        "triage_thresholds_from_full_data": triage,
        "output_csv": str(OUT_CSV),
        "saved_model": str(MODEL_PATH),
        "saved_meta": str(META_PATH),
    }


def _pretty_print(rep: Dict[str, Any]) -> None:
    print("\n=== Calibration Report ===")
    print("Features:", rep["features_used"])
    print(f"Test AUROC: {rep['test_auroc']:.3f}")
    b = rep["best_threshold_on_test"]
    print(
        f"Best threshold (by F1 on test): {b['thr']:.2f} | "
        f"P={b['precision']:.3f} R={b['recall']:.3f} F1={b['f1']:.3f}"
    )
    t = rep["triage_thresholds_from_full_data"]
    print("Suggested triage probability thresholds:")
    print(f"  Low→Med: {t['low_to_med_prob']:.3f}")
    print(f"  Med→High: {t['med_to_high_prob']:.3f}")
    print(f"  High→Critical: {t['high_to_critical_prob']:.3f}")
    print(f"Saved CSV: {rep['output_csv']}")
    print(f"Saved model: {rep['saved_model']}")
    print(f"Saved meta: {rep['saved_meta']}")
    print("==========================\n")


if __name__ == "__main__":
    rep = fit_calibration()
    _pretty_print(rep)