"""backend/risk_scoring.py

Core scoring utilities for the "PCA + bounded LLM" hybrid design.
All outputs are *per-user* (one row per Username).
"""

from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler


def latest_unified_csv(analysis_dir: str = "analysis_output") -> str:
    files = sorted(glob.glob(str(Path(analysis_dir) / "unified_instagram_analysis_*.csv")))
    if not files:
        raise FileNotFoundError(f"No unified_instagram_analysis_*.csv found under: {analysis_dir}")
    return files[-1]


def _safe_bool_series(s: pd.Series) -> pd.Series:
    return s.astype(str).str.lower().isin(["true", "1", "yes", "y", "t"]).astype(float)


def _percentile(arr: np.ndarray, q: float) -> float:
    arr = np.asarray(arr, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) == 0:
        return 0.0
    return float(np.percentile(arr, q))


def build_user_feature_table(raw: pd.DataFrame) -> pd.DataFrame:
    """Aggregate comment-level signals into one row per user."""
    df = raw.copy()

    if "Username" not in df.columns:
        raise ValueError("Unified CSV must contain Username column.")

    # Ensure numeric columns exist
    for col in ["Anger_Score", "Sadness_Score", "Fear_Score", "Distortion_Score", "Distortion_Ratio"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Sentiment: treat negative as risk signal (stable with your schema)
    sent = df.get("Sentiment", "").astype(str).str.lower()
    df["is_negative"] = sent.eq("negative").astype(float)

    # Distortion flag
    if "Distortion_Indicator" in df.columns:
        df["distortion_flag"] = _safe_bool_series(df["Distortion_Indicator"])
    elif "Has_Cognitive_Distortions" in df.columns:
        df["distortion_flag"] = _safe_bool_series(df["Has_Cognitive_Distortions"])
    else:
        df["distortion_flag"] = 0.0

    # Per-comment distress emotion composite
    df["emotion_comment"] = df[["Anger_Score", "Sadness_Score", "Fear_Score"]].mean(axis=1)

    # Per-comment harm intensity (bounded)
    df["harm_intensity"] = np.tanh((df["Distortion_Score"].fillna(0.0).astype(float)) / 2.0)

    rows = []
    for user, g in df.groupby("Username", dropna=True):
        total_comments = int(len(g))

        # Emotion accumulation: baseline + spikes
        emo_mean = float(np.nanmean(g["emotion_comment"].values))
        emo_p90 = _percentile(g["emotion_comment"].values, 90)
        emotion_score = 0.7 * emo_mean + 0.3 * emo_p90

        # Sentiment accumulation: fraction negative + spike flag
        neg_mean = float(np.nanmean(g["is_negative"].values))
        neg_p90 = _percentile(g["is_negative"].values, 90)  # 1 if any negative in tail
        sentiment_score = 0.8 * neg_mean + 0.2 * neg_p90

        # Harm accumulation: distortion rate + intensity tail
        dist_rate = float(np.nanmean(g["distortion_flag"].values))
        harm_p90 = _percentile(g["harm_intensity"].values, 90)
        harm_score = 0.6 * dist_rate + 0.4 * harm_p90

        # Missingness / low-data damping: avoid overconfidence for tiny histories
        damp = min(1.0, float(np.sqrt(total_comments / 5.0))) if total_comments > 0 else 0.0
        emotion_score *= damp
        sentiment_score *= damp
        harm_score *= damp

        # Evidence snippet (deterministic, not LLM)
        snippet = ""
        if "Text" in g.columns:
            texts = g["Text"].dropna().astype(str).head(3).tolist()
            snippet = " | ".join([t[:180] for t in texts])

        rows.append(
            {
                "case_id": str(user),
                "Username": str(user),
                "total_comments": total_comments,
                "emotion_mean": emo_mean,
                "emotion_p90": emo_p90,
                "sentiment_neg_mean": neg_mean,
                "sentiment_neg_p90": neg_p90,
                "distortion_rate": dist_rate,
                "harm_p90": harm_p90,
                "emotion_score": float(np.clip(emotion_score, 0.0, 1.0)),
                "sentiment_score": float(np.clip(sentiment_score, 0.0, 1.0)),
                "harm_score": float(np.clip(harm_score, 0.0, 1.0)),
                "evidence_snippet": snippet,
            }
        )

    out = pd.DataFrame(rows)

    # Ensure we have at least 1 row
    if out.empty:
        raise ValueError("No users found. Check Username values in the unified CSV.")

    return out


def _minmax01(arr: np.ndarray) -> np.ndarray:
    arr = np.asarray(arr, dtype=float)
    mn, mx = float(np.min(arr)), float(np.max(arr))
    if mx - mn < 1e-9:
        return np.zeros_like(arr, dtype=float)
    return (arr - mn) / (mx - mn)


def compute_pca_risk_scores(users: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    """Run PCA on standardized (emotion_score, sentiment_score, harm_score)."""
    df = users.copy()
    feats = ["emotion_score", "sentiment_score", "harm_score"]
    X = df[feats].astype(float).to_numpy()

    scaler = StandardScaler()
    Xz = scaler.fit_transform(X)

    pca = PCA(n_components=1, random_state=7)
    pc1 = pca.fit_transform(Xz).reshape(-1)

    df["pc1_raw"] = pc1
    df["risk_score_math"] = 1 / (1 + np.exp(-0.75 * pc1))

    w = pca.components_[0].reshape(-1)
    meta = {
        "pc1_loadings": {feats[i]: float(w[i]) for i in range(len(feats))},
        "explained_variance_ratio_pc1": float(pca.explained_variance_ratio_[0]),
        "n_cases": int(len(df)),
    }
    return df, meta
