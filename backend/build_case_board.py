"""backend/build_case_board.py

Builds a *per-user* case board from the newest unified_instagram_analysis_*.csv.

Correct scoring logic (no ground truth, small N ~ 20 users):
1) Aggregate comment-level signals -> one row per user ("case")
2) Compute stable group scores: emotion_score / sentiment_score / harm_score
3) Standardize and run PCA on the 3 group scores
   - PC1 loadings = learned weights
   - PC1 score -> minmax normalize -> risk_score_math in [0,1]
4) Bounded LLM refinement: delta in [-0.10, +0.10]
   - final_score = clamp(risk_score_math + delta, 0, 1)

This matches the requested: PCA weight learning + deterministic score + bounded LLM layer.
"""

from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from risk_scoring import (
    latest_unified_csv,
    build_user_feature_table,
    compute_pca_risk_scores,
)
from decision_layer import stable_llm_refinement, make_ollama_caller


def build_case_board_from_unified(
    analysis_dir: str = "analysis_output",
    out_path: str = "case_board.csv",
    *,
    enable_llm: bool = False,
    ollama_model: str = "llama3.2:3b",
) -> pd.DataFrame:
    """Create per-user case board CSV.

    If enable_llm=True, this will call Ollama (local) and add a bounded delta.
    Keep enable_llm=False for deterministic runs (recommended for dev/tests).
    """
    path = latest_unified_csv(analysis_dir)
    raw = pd.read_csv(path)

    users = build_user_feature_table(raw)

    # PCA-based learned weights + risk score
    users, pca_meta = compute_pca_risk_scores(users)

    # Deterministic base score
    users["BaseScore"] = users["risk_score_math"].astype(float)

    # Monotonic sanity: if harm_score rises a lot, score shouldn't go down
    users["BaseScore"] = np.maximum(users["BaseScore"].astype(float), 0.40 * users["harm_score"].astype(float))
    users["BaseScore"] = np.clip(users["BaseScore"], 0.0, 1.0)

    # Optional LLM bounded delta refinement
    users["delta"] = 0.0
    users["FinalRiskScore"] = users["BaseScore"].astype(float)

    if enable_llm:
        call_llm = make_ollama_caller(model=ollama_model)
        deltas = []
        finals = []
        reasons = []
        for _, r in users.iterrows():
            final, info = stable_llm_refinement(
                base_score=float(r["BaseScore"]),
                emotion_score=float(r["emotion_score"]),
                sentiment_score=float(r["sentiment_score"]),
                harm_score=float(r["harm_score"]),
                evidence_text=str(r.get("evidence_snippet", ""))[:1200],
                call_llm=call_llm,
            )
            deltas.append(float(info.get("chosen_delta", info.get("delta", 0.0))))
            finals.append(float(final))
            reasons.append(info)
        users["delta"] = deltas
        users["FinalRiskScore"] = finals
        users["llm_meta"] = [json.dumps(x, ensure_ascii=False) for x in reasons]
    else:
        users["llm_meta"] = json.dumps({"enabled": False})

    # Build compact explanation payload (deterministic, safe for UI)
    def _top_reasons(row: pd.Series):
        reasons = []
        reasons.append({"signal": "harm_score", "value": float(row["harm_score"])})
        reasons.append({"signal": "emotion_score", "value": float(row["emotion_score"])})
        reasons.append({"signal": "sentiment_score", "value": float(row["sentiment_score"])})
        # include spike features if present
        reasons.append({"signal": "emotion_p90", "value": float(row.get("emotion_p90", 0.0))})
        reasons.append({"signal": "distortion_rate", "value": float(row.get("distortion_rate", 0.0))})
        return reasons[:5]

    users["explanation_signals"] = users.apply(
        lambda r: json.dumps(
            {
                "summary": "PCA math score (PC1) on user-level emotion/sentiment/harm + optional bounded LLM delta.",
                "top_reasons": _top_reasons(r),
                "feature_snapshot": {
                    "total_comments": int(r.get("total_comments", 0)),
                    "emotion_score": float(r["emotion_score"]),
                    "sentiment_score": float(r["sentiment_score"]),
                    "harm_score": float(r["harm_score"]),
                    "risk_score_math": float(r["risk_score_math"]),
                    "base_score": float(r["BaseScore"]),
                    "delta": float(r["delta"]),
                    "final_score": float(r["FinalRiskScore"]),
                },
                "pca_pc1_loadings": pca_meta.get("pc1_loadings", {}),
                "model_version": "pca_v1_user_level",
            },
            ensure_ascii=False,
        ),
        axis=1,
    )

    # Triage labels (simple quantile-based)
    q_med = float(users["FinalRiskScore"].quantile(0.60)) if len(users) >= 5 else 0.50
    q_high = float(users["FinalRiskScore"].quantile(0.80)) if len(users) >= 5 else 0.70
    q_crit = float(users["FinalRiskScore"].quantile(0.90)) if len(users) >= 10 else 0.85

    def _bucket(x: float) -> str:
        if x >= q_crit:
            return "Critical"
        if x >= q_high:
            return "High"
        if x >= q_med:
            return "Medium"
        return "Low"

    users["Overall_Risk_Level"] = users["FinalRiskScore"].astype(float).apply(_bucket)

    # Required output cols for UI
    out_cols = [
        "case_id",
        "Username",
        "total_comments",
        "emotion_score",
        "sentiment_score",
        "harm_score",
        "risk_score_math",
        "BaseScore",
        "delta",
        "FinalRiskScore",
        "Overall_Risk_Level",
        "evidence_snippet",
        "explanation_signals",
        "llm_meta",
    ]
    for c in out_cols:
        if c not in users.columns:
            users[c] = np.nan

    users[out_cols].to_csv(out_path, index=False)
    return users[out_cols]


if __name__ == "__main__":
    build_case_board_from_unified("analysis_output", "case_board.csv", enable_llm=False)
    print("Wrote case_board.csv")
