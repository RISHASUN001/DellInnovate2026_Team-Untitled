# backend/evaluation/scorecard_eval.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Dict, Any, List, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_fscore_support, roc_auc_score


ROOT = Path(__file__).resolve().parents[1]  # backend/
DEFAULT_STAGE2 = ROOT / "stage2_user_analysis.csv"


@dataclass
class RankingMetrics:
    k: int
    precision_at_k: float
    recall_at_k: float
    hit_rate_at_k: float


def _ensure_bool(x) -> bool:
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return bool(int(x))
    if isinstance(x, str):
        return x.strip().lower() in {"true", "1", "yes", "y"}
    return False


def precision_recall_f1(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    p, r, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
    return {"precision": float(p), "recall": float(r), "f1": float(f1)}


def ranking_metrics(df, label_col, score_col, ks=(5,10,20), higher_score_higher_risk=True):
    y = df[label_col].astype(bool).to_numpy()
    scores = df[score_col].astype(float).to_numpy()

    order = np.argsort(scores)
    if higher_score_higher_risk:
        order = order[::-1]
    y_sorted = y[order]

    total_pos = int(y.sum())
    out = []

    # clip then dedupe
    clipped = [max(1, min(int(k), len(df))) for k in ks]
    clipped_unique = []
    for k in clipped:
        if k not in clipped_unique:
            clipped_unique.append(k)

    for k in clipped_unique:
        topk = y_sorted[:k]
        tp = int(topk.sum())
        precision_k = tp / k
        recall_k = tp / total_pos if total_pos > 0 else 0.0
        hit_rate_k = 1.0 if tp > 0 else 0.0
        out.append(RankingMetrics(
            k=k,
            precision_at_k=precision_k,
            recall_at_k=recall_k,
            hit_rate_at_k=hit_rate_k
        ))

    return out


def evaluate_stage2(
    stage2_path: Path = DEFAULT_STAGE2,
    label_col: str = "Requires_Attention",
    score_col: str = "Risk_Score",
    threshold: float | None = None,
) -> Dict[str, Any]:
    df = pd.read_csv(stage2_path)

    # Normalize label
    df[label_col] = df[label_col].apply(_ensure_bool)

    # Default threshold: if none, pick something reasonable: median of scores among all users
    scores = df[score_col].astype(float)
    if threshold is None:
        threshold = float(scores.median())

    # Binary decision from score
    y_true = df[label_col].astype(bool).to_numpy()
    y_score = scores.to_numpy()
    y_pred = (y_score >= threshold)

    cls = precision_recall_f1(y_true, y_pred)

    # AUROC only if both classes exist
    auc = None
    if len(np.unique(y_true)) == 2:
        auc = float(roc_auc_score(y_true, y_score))

    n = len(df)
    ks = sorted(set([min(n, k) for k in (3, 5, 10) if min(n, k) >= 1]))
    ranks = ranking_metrics(df, label_col=label_col, score_col=score_col, ks=ks)

    return {
        "n_users": int(len(df)),
        "positives": int(y_true.sum()),
        "threshold_used": float(threshold),
        "classification": cls,
        "auroc": auc,
        "ranking": [m.__dict__ for m in ranks],
    }


def _pretty_print(report: Dict[str, Any]) -> None:
    print("\n=== Scorecard Evaluation (Stage2) ===")
    print(f"Users: {report['n_users']} | Positives(label=1): {report['positives']}")
    print(f"Threshold (Risk_Score >=): {report['threshold_used']:.3f}")
    cls = report["classification"]
    print(f"Precision: {cls['precision']:.3f} | Recall: {cls['recall']:.3f} | F1: {cls['f1']:.3f}")
    if report["auroc"] is not None:
        print(f"AUROC: {report['auroc']:.3f}")
    print("\nRanking:")
    for m in report["ranking"]:
        print(
            f"  P@{m['k']}: {m['precision_at_k']:.3f} | "
            f"R@{m['k']}: {m['recall_at_k']:.3f} | "
            f"Hit@{m['k']}: {m['hit_rate_at_k']:.3f}"
        )
    print("====================================\n")


if __name__ == "__main__":
    rep = evaluate_stage2()
    _pretty_print(rep)