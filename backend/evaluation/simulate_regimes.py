# backend/evaluation/simulate_regimes.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
import pandas as pd

from evaluation.scorecard_eval import ranking_metrics


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "synthetic_regime_users.csv"


@dataclass
class SimConfig:
    n_users: int = 80
    crisis_frac: float = 0.25
    n_comments_per_user: int = 25
    seed: int = 7


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def generate_synthetic_users(cfg: SimConfig) -> pd.DataFrame:
    rng = np.random.default_rng(cfg.seed)

    users = [f"user_{i:03d}" for i in range(cfg.n_users)]
    is_crisis = rng.random(cfg.n_users) < cfg.crisis_frac

    rows = []
    for u, crisis in zip(users, is_crisis):
        # Base sentiment around mild negative/neutral
        base = rng.normal(loc=-0.2, scale=0.3, size=cfg.n_comments_per_user)

        # Crisis burst: a block of comments becomes sharply negative + volatile
        if crisis:
            start = rng.integers(5, cfg.n_comments_per_user - 8)
            base[start : start + 6] += rng.normal(loc=-1.2, scale=0.4, size=6)

        # Recovery: last few improve slightly
        base[-5:] += rng.normal(loc=0.5, scale=0.2, size=5)

        # Convert to (0,1) "negative probability" proxy
        neg_prob = _sigmoid(-base)

        # Distortion: higher during crisis
        dist_rate = float(rng.uniform(0.05, 0.2))
        if crisis:
            dist_rate += float(rng.uniform(0.3, 0.6))

        # Volatility: std of sentiment
        vol = float(np.std(base))

        # Simple "risk score"
        risk_score = 50 * float(np.mean(neg_prob)) + 25 * dist_rate + 10 * vol

        rows.append(
            {
                "Username": u,
                "synthetic_crisis_label": bool(crisis),
                "Distortion_Rate": dist_rate,
                "Volatility_Score": vol,
                "Risk_Score_synth": risk_score,
                "n_comments": cfg.n_comments_per_user,
            }
        )

    return pd.DataFrame(rows)


def run_simulation(cfg: SimConfig = SimConfig()) -> Dict[str, Any]:
    df = generate_synthetic_users(cfg)
    df.to_csv(OUT, index=False)

    ranks = ranking_metrics(
        df,
        label_col="synthetic_crisis_label",
        score_col="Risk_Score_synth",
        ks=(5, 10, 20),
        higher_score_higher_risk=True,
    )

    return {"output_csv": str(OUT), "ranking": [m.__dict__ for m in ranks]}


def _pretty_print(rep: Dict[str, Any]) -> None:
    print("\n=== Synthetic Regime Stress Test ===")
    for m in rep["ranking"]:
        print(
            f"P@{m['k']}={m['precision_at_k']:.3f} | "
            f"R@{m['k']}={m['recall_at_k']:.3f} | "
            f"Hit@{m['k']}={m['hit_rate_at_k']:.3f}"
        )
    print(f"Saved: {rep['output_csv']}")
    print("===================================\n")


if __name__ == "__main__":
    rep = run_simulation()
    _pretty_print(rep)