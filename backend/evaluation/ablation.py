# backend/evaluation/ablation.py
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_fscore_support

from evaluation.scorecard_eval import ranking_metrics, _ensure_bool


ROOT = Path(__file__).resolve().parents[1]
STAGE1 = ROOT / "stage1_signal_data.csv"
STAGE2 = ROOT / "stage2_user_analysis.csv"


def _prf(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    p, r, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
    return {"precision": float(p), "recall": float(r), "f1": float(f1)}


def _aggregate_emotion_score_stage1(stage1: pd.DataFrame) -> pd.DataFrame:
    """
    Build a user-level 'emotion risk' signal from stage1.
    We use:
      - mean negative sentiment score
      - mean sadness/fear/anger
      - distortion indicator rate
    """
    df = stage1.copy()
    df["Sentiment"] = df["Sentiment"].astype(str).str.lower()
    df["neg_sent_score"] = np.where(df["Sentiment"].eq("negative"), df["Sentiment_Score"].astype(float), 0.0)

    # robust: if some columns missing, fill with zeros
    for col in ["Sadness_Score", "Fear_Score", "Anger_Score"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = df[col].astype(float)

    df["emo_triplet"] = (df["Sadness_Score"] + df["Fear_Score"] + df["Anger_Score"]) / 3.0

    if "Distortion_Indicator" in df.columns:
        df["Distortion_Indicator"] = df["Distortion_Indicator"].apply(_ensure_bool)
        df["dist_ind"] = df["Distortion_Indicator"].astype(int)
    else:
        df["dist_ind"] = 0

    agg = (
        df.groupby("User", as_index=False)
        .agg(
            emotion_only_score=("emo_triplet", "mean"),
            neg_sent_mean=("neg_sent_score", "mean"),
            distortion_ind_rate=("dist_ind", "mean"),
            n_comments=("Comment_Text", "count"),
        )
    )

    # emotion-only combined (simple weighted)
    # weights chosen for interpretability; you can tune later
    agg["score_A_emotion_only"] = 60 * agg["emotion_only_score"] + 40 * agg["neg_sent_mean"]
    return agg


def _engagement_adjustment(stage2: pd.DataFrame) -> pd.Series:
    """
    Map engagement pattern strings to an additive risk adjustment.
    Designed to be explainable.
    """
    if "Engagement_Pattern" not in stage2.columns:
        return pd.Series(np.zeros(len(stage2)), index=stage2.index)

    pattern = stage2["Engagement_Pattern"].astype(str).str.lower()

    adj = np.zeros(len(stage2), dtype=float)

    # If your service uses these labels (repo shows examples)
    adj += np.where(pattern.eq("crisis_burst"), 8.0, 0.0)
    adj += np.where(pattern.eq("concerning_content"), 5.0, 0.0)
    adj += np.where(pattern.eq("withdrawal"), 6.0, 0.0)

    # Normal/minimal: no extra
    return pd.Series(adj, index=stage2.index)


def run_ablation(
    stage1_path: Path = STAGE1,
    stage2_path: Path = STAGE2,
    label_col: str = "Requires_Attention",
) -> Dict[str, Any]:
    s1 = pd.read_csv(stage1_path)
    s2 = pd.read_csv(stage2_path)

    # normalize label
    s2[label_col] = s2[label_col].apply(_ensure_bool)

    # --- Build Score A from stage1 ---
    emo = _aggregate_emotion_score_stage1(s1)

    # --- Merge into stage2 for shared label & per-user features ---
    merged = s2.merge(emo, left_on="Username", right_on="User", how="left")

    # fill missing
    for col in ["score_A_emotion_only", "Distortion_Rate", "Volatility_Score", "Rapid_Shifts"]:
        if col in merged.columns:
            merged[col] = merged[col].fillna(0.0)

    # --- Score B: emotion + distortion ---
    # Distortion_Rate is already in stage2; scale to comparable range
    merged["score_B_plus_distortion"] = merged["score_A_emotion_only"] + 20.0 * merged["Distortion_Rate"].astype(float)

    # --- Score C: emotion + distortion + volatility + engagement ---
    vol = merged["Volatility_Score"].astype(float)
    shifts = merged.get("Rapid_Shifts", pd.Series(np.zeros(len(merged)))).astype(float)
    engage_adj = _engagement_adjustment(merged)

    merged["score_C_full"] = (
        merged["score_B_plus_distortion"]
        + 10.0 * vol
        + 3.0 * shifts
        + engage_adj
    )

    # Evaluate each score with a threshold = median score (simple, stable)
    results = {}

    for name, score_col in [
        ("A_emotion_only", "score_A_emotion_only"),
        ("B_plus_distortion", "score_B_plus_distortion"),
        ("C_full", "score_C_full"),
    ]:
        scores = merged[score_col].astype(float).to_numpy()
        thr = float(np.median(scores))
        y_true = merged[label_col].astype(bool).to_numpy()
        y_pred = scores >= thr

        cls = _prf(y_true, y_pred)
        ranks = ranking_metrics(merged, label_col=label_col, score_col=score_col, ks=(5, 10, 20))

        results[name] = {
            "threshold_used": thr,
            "classification": cls,
            "ranking": [m.__dict__ for m in ranks],
        }

    return results


def _pretty_print(res: Dict[str, Any]) -> None:
    print("\n=== Ablation Study ===")
    for k, v in res.items():
        cls = v["classification"]
        print(f"\n[{k}] threshold={v['threshold_used']:.3f}")
        print(f"  Precision={cls['precision']:.3f} | Recall={cls['recall']:.3f} | F1={cls['f1']:.3f}")
        for m in v["ranking"]:
            print(
                f"  P@{m['k']}={m['precision_at_k']:.3f} | "
                f"R@{m['k']}={m['recall_at_k']:.3f} | "
                f"Hit@{m['k']}={m['hit_rate_at_k']:.3f}"
            )
    print("======================\n")


if __name__ == "__main__":
    out = run_ablation()
    _pretty_print(out)